import datetime as dt

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from weather_utils import (
    InvalidAPIKeyError,
    determine_current_season,
    sequential_analyze,
    is_temperature_normal,
    get_current_temperature_sync
)

st.set_page_config(layout="wide")

st.title("Анализ температуры по городам")

uploaded_file = st.file_uploader("Загрузите файл с историческими данными", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file, parse_dates=['timestamp'])
    
    # Анализ данных
    with st.spinner('Анализируем данные...'):
        results = sequential_analyze(df)
    
    # Выбор города
    cities = [res['city'] for res in results]
    selected_city = st.selectbox("Выберите город", cities)

    city_analysis = next((item for item in results if item["city"] == selected_city), None)
    
    st.header("Описательная статистика")
    st.write(f"Средняя температура: {city_analysis['average_temp']:.2f} °C")
    st.write(f"Минимальная температура: {city_analysis['min_temp']:.2f} °C")
    st.write(f"Максимальная температура: {city_analysis['max_temp']:.2f} °C")

    st.header("Временной ряд температур с аномалиями")
    city_df = df[df['city'] == selected_city].sort_values('timestamp')
    anomalies = pd.DataFrame(city_analysis['anomalies'])

    fig = px.line(
        city_df,
        x='timestamp',
        y='temperature',
        labels={'temperature': 'Температура (°C)', 'timestamp': 'Дата'},
        markers=True,
        height=800
    )
    
    if not anomalies.empty:
        fig.add_trace(
            go.Scatter(
                x=anomalies['timestamp'],
                y=anomalies['temperature'],
                mode='markers',
                marker=dict(color='red', size=10, symbol='diamond'),
                name='Аномалии'
            )
        )

    trend = city_analysis['trend']
    trend_color = 'green' if trend == 'positive' else 'red'
    trend_text = 'Положительный' if trend == 'positive' else 'Отрицательный'
    
    fig.add_annotation(
        x=0.5,
        y=1.05,
        xref='paper',
        yref='paper',
        text=f"Тренд: {trend_text}",
        showarrow=False,
        font=dict(
            size=18,
            color=trend_color
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.header("Сезонные профили")
    st.dataframe(pd.DataFrame(city_analysis['seasonal_profile']), hide_index=True)

    st.header("Текущая температура")
    api_key = st.text_input("Введите ваш OpenWeatherMap API Key", type="password")
    
    if api_key:
        city_name = selected_city
        # Получение текущего сезона и температуры
        current_season = determine_current_season(dt.datetime.now().date())
        try:
            current_temp = get_current_temperature_sync(city_name, api_key)
        except InvalidAPIKeyError as e:
            st.error(e.detail)
        else:
            st.write(f"Текущая температура в {city_name}: {current_temp} °C")

            normal = is_temperature_normal(city_analysis, current_temp, current_season)
            if normal:
                st.success("Температура нормальная для текущего сезона.")
            else:
                st.error("Температура аномальная для текущего сезона.")
    else:
        st.info("Введите API-ключ для отображения текущей температуры.")
