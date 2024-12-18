import requests
import numpy as np
from sklearn.linear_model import LinearRegression


class InvalidAPIKeyError(Exception):
    detail = 'Некорректный API-ключ'


def analyze_city(city, df_city):
    result = {}
    result['city'] = city
    
    # Скользящее среднее и стандартное отклонение
    df_city = df_city.sort_values('timestamp')
    df_city['rolling_mean'] = df_city['temperature'].rolling(window=30, min_periods=1).mean()
    df_city['rolling_std'] = df_city['temperature'].rolling(window=30, min_periods=1).std().fillna(0)
    
    # Аномалии по скользящему окну
    df_city['anomaly'] = (np.abs(df_city['temperature'] - df_city['rolling_mean']) > 2 * df_city['rolling_std'])
    result['anomalies'] = df_city[df_city['anomaly']][['timestamp', 'temperature']].to_dict('records')

    # Профиль сезона
    result['seasonal_profile'] = df_city.groupby('season')['temperature'].agg([
        'mean',
        'std'
    ]).reset_index().to_dict('records')

    # Тренд
    df_city['day_number'] = (df_city['timestamp'] - df_city['timestamp'].min()).dt.days
    X = df_city[['day_number']]
    y = df_city['temperature']
    model = LinearRegression()
    model.fit(X, y)
    slope = model.coef_[0]
    result['trend'] = 'positive' if slope > 0 else 'negative'

    # Средняя, минимальная и максимальная температура
    result['average_temp'] = df_city['temperature'].mean()
    result['min_temp'] = df_city['temperature'].min()
    result['max_temp'] = df_city['temperature'].max()

    return result


# Распараллеливание не ускорило анализ, а наоборот замедлило
# Последовательный анализ занял ~0.09 сек
# Параллельный анализ занял 1.5 сек
# Поэтому решено было оставить последовательный анализ
def sequential_analyze(df):
    cities = df['city'].unique()
    results = []
    for city in cities:
        df_city = df[df['city'] == city].copy()
        result = analyze_city(city, df_city)
        results.append(result)
    return results


# В ходе тестирования на нескольких городах лучше себя показал асинхронный подход
# Синхронные запросы заняли ~2.08 сек
# Асинхронные запросы заняли ~0.18 сек
# Но, так как в приложении streamlit нужна темпертарура для одного города, можно использовать синхронные запросы 
def get_current_temperature_sync(city, api_key):
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            'q': city,
            'appid': api_key,
            'units': 'metric'
        }
    )
    if response.status_code == 401:
        raise InvalidAPIKeyError()
    return response.json()['main']['temp']


# Получение сезона из даты
def determine_current_season(date):
    month = date.month
    if month in [12, 1, 2]:
        return 'winter'
    elif month in [3, 4, 5]:
        return 'spring'
    elif month in [6, 7, 8]:
        return 'summer'
    else:
        return 'autumn'


# Проверка на нормальность температуры
def is_temperature_normal(city_analysis, current_temp, season):
    for profile in city_analysis['seasonal_profile']:
        if profile['season'] == season:
            mean = profile['mean']
            std = profile['std']
            break
    else:
        return True

    return np.abs(current_temp - mean) <= 2 * std
