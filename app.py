import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
import os
import zipfile

"""
Aquí definimos la configuración general de la página
"""
st.set_page_config(
    page_title="Dashboard Ventas - Práctica Streamlit Mateo",
    page_icon="📈",
    layout="wide",
) #esto no permite definir el título del navegador, el icono y usamos wide que nos permite aprovechar todo el ancho

def read_csv_from_zip(zip_path: str) -> pd.DataFrame:
    if not os.path.exists(zip_path):
        st.error(f"No existe el archivo {zip_path} en el repo.")
        st.stop()

    with zipfile.ZipFile(zip_path, "r") as z:
        infos = [i for i in z.infolist() if i.filename.lower().endswith(".csv")]

        # DEBUG útil: ver qué hay dentro
        if not infos:
            st.error(f"{zip_path} NO contiene ningún .csv. Contenido: {z.namelist()[:50]}")
            st.stop()

        # Elegimos el CSV más grande (normalmente el dataset real)
        best = max(infos, key=lambda i: i.file_size)

        if best.file_size == 0:
            st.error(f"El CSV dentro de {zip_path} está vacío: {best.filename}")
            st.stop()

        with z.open(best) as f:
            # Leemos directamente el CSV del zip (sin extraer a disco)
            return pd.read_csv(f, low_memory=False)

#####################################################################

# Cargamos los datos


@st.cache_data #sirve para que streamlit no lea de nuevo los csv cada vez que movemos algún filtro en la página (ganamos en velocidad)
def load_data():
   
    df1 = read_csv_from_zip("parte_1.zip")
    df2 = read_csv_from_zip("parte_2.zip")
    df = pd.concat([df1, df2], ignore_index=True)
    
    # Hemos usado pandas para cargar los archivos csv y los pega
    # uno encima de otro para crear un único dataframe. Usamos
    # ignore_index para reasignar correctamente los índices en el nuevo
    # dataframe grande.
    
    
    if "Unnamed: 0" in df.columns: #si aparece una columna "Unnamed 0" (que suele venir de un índice guardado por error) la borramos del dataframe
        df = df.drop(columns=["Unnamed: 0"]) #elimina la columna con ese nombre

    df["date"] = pd.to_datetime(df["date"], errors="coerce") #nos permite convertir los strings a fechas reales.
    
    
    df["store_nbr"] = pd.to_numeric(df["store_nbr"], errors="coerce").astype("Int64") #ponemos el número de tienda en Int64
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0.0) #nos permite rellenar los Nan con 0
    df["onpromotion"] = pd.to_numeric(df["onpromotion"], errors="coerce").fillna(0).astype(int) #si falta, entonces ponemos 0. Pasamos a entero
    
    if "year" not in df.columns: #si el csv viene con la columna year entonces lo usa
        df["year"] = df["date"].dt.year
    if "month" not in df.columns:
        df["month"] = df["date"].dt.month
    if "week" not in df.columns:
        df["week"] = df["date"].dt.isocalendar().week.astype(int)
    #hacemos esto con las columnas year,month,week por  si no vienen ya definidas (permite robustez en el código)
    
    return df

df = load_data() 
######################################################################

# Tabla auxiliar de transacciones.

# El problema es que transactions suele venir repetido para cada family 
# de esa tienda y fecha.

# Para solucionarlo nos creamos un dataframe de transacciones que no tenga
# duplicados. Es decir, que tenga una sola fila por (date,store). Con esto
# nos evitaremos sumar transacciones varias veces.

@st.cache_data
def build_transactions_table(df_):
    cols = ["date", "store_nbr", "state", "city", "transactions", "year"]
    cols = [c for c in cols if c in df_.columns] #verificamos que son columnas existentes del dataframe
    base = df_[cols].drop_duplicates(subset=["date", "store_nbr"]) #nos quedamos con una sola fila
    base["transactions"] = pd.to_numeric(base["transactions"], errors="coerce").fillna(0.0) #si no hay transacción 0
    return base

df_tx = build_transactions_table(df)

#######################################################################


######################################################################
st.title("Dashboard de Ventas (Streamlit)")
st.caption("KPIs y visualizaciones para CEO y Dirección de Ventas")

with st.sidebar: #nos permite creaer un selector de fecha
    st.header("⚙️ Controles")
    st.write("Este panel filtra el dataset completo.")

    #definimos el rango con min y max de la fecha
    min_date = df["date"].min() 
    max_date = df["date"].max()

    date_range = st.date_input(
        "Rango de fechas",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    ) #devuelve una tupla con la fecha de inicio y fecha final (date_inicio, date_fin)
    
    start_date = pd.to_datetime(date_range[0]) #fecha de inicio
    end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1) #si solo consideramos el final python excluye todo el día 31 salvo las ventas a medianoche. Por tanto esta línea sirve para incluir todo el último día seleccionado

df_f = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy() #nos permite quedarnos con las fechas que estén dentro dentro del rango elegido -- df_f son las ventas (por producto)
df_tx_f = df_tx[(df_tx["date"] >= start_date) & (df_tx["date"] <= end_date)].copy() #transacciones (una fila por tienda y día)

tabs = st.tabs(["1) Visión global", "2) Por tienda", "3) Por estado", "4) Insights extra"])

# Se aplica un filtro global de fechas que nos permite analizar
# cualquier periodo del dataset. Esto facilita el estudio de la 
#evolución temporal de las ventas.

#######################################################################################

with tabs[0]:
    st.subheader("a) Visión global de las ventas")

    #a)
    total_stores = int(df_f["store_nbr"].nunique()) #nos permite determinar cúantas tiendes distintas hay en el periodo que hemos seleccionado
    total_products = int(df_f["family"].nunique()) if "family" in df_f.columns else 0 #determina cúantas familias de producto distintas se venden
    total_states = int(df_f["state"].nunique()) if "state" in df_f.columns else 0 #determina en cúantos estados opera la empresa

    
    ym = df_f["date"].dt.to_period("M").astype(str) #
    total_months = int(ym.nunique())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nº total de tiendas", f"{total_stores:,}")
    c2.metric("Nº total de productos (families)", f"{total_products:,}")
    c3.metric("Nº de estados", f"{total_states:,}")
    c4.metric("Nº de meses con datos", f"{total_months:,}")

    st.divider()


    # b) Análisis en términos medios
    # =========================================================

    st.subheader("b) Análisis en términos medios")

    # -----------------------------
    # i. Top 10 productos más vendidos
    # -----------------------------
    top_products = (df.groupby("family")["sales"].sum().sort_values(ascending=False).head(10).reset_index())

    fig_top_products = px.bar(
        top_products,
        x="sales",
        y="family",
        orientation="h",
        title="Top 10 productos más vendidos",
        color="sales",
        color_continuous_scale="Blues"
    )

    fig_top_products.update_layout(
        yaxis=dict(categoryorder="total ascending"),
        height=450
    )

    st.plotly_chart(fig_top_products, use_container_width=True)


    # -----------------------------
    # ii. Distribución de ventas por tiendas (todas las tiendas)
    # -----------------------------
    """
    Se mete colores para diferenciar mejor una barra de otra, y que la claridad de la barra vaya en consonancia con el número de ventas logrado por tienda, ya que la haber tantas barras es importante asegurar una buena visualización.
    """
    sales_store = (df.groupby("store_nbr")["sales"].sum().sort_values(ascending=False).reset_index())

    # Forzamos a categórico para evitar huecos
    sales_store["store_nbr"] = sales_store["store_nbr"].astype(str)

    fig_store_all = px.bar(
        sales_store,
        x="store_nbr",
        y="sales",
        title="Ventas totales por tienda",
        color="sales",
        color_continuous_scale="Teal"
    )

    fig_store_all.update_layout(
        xaxis_title="Tienda",
        yaxis_title="Ventas totales",
        height=500,
        xaxis=dict(
            type="category",
            categoryorder="total descending",   # ordenadas de mayor a menor
            tickangle=-45                      # gira etiquetas para que se lean bien
        )
    )

    st.plotly_chart(fig_store_all, use_container_width=True)

    # -----------------------------
    # iii. Top 10 tiendas con más ventas en productos en promoción
    # -----------------------------
    """
    En este apartado, para evitar espacios entre barras, el eje X se cambia a categórico. Asimismo, se vuelve a 
    usar colores cuya claridad indica el numero de ventas, para mejorar la visualización.
    """
    promo_sales = (df[df["onpromotion"] > 0].groupby("store_nbr")["sales"].sum().sort_values(ascending=False).head(10).reset_index())

    # Forzamos categórico y orden visual
    promo_sales["store_nbr"] = promo_sales["store_nbr"].astype(str)
    order = promo_sales.sort_values("sales")["store_nbr"].tolist()

    fig_top_promo = px.bar(
        promo_sales,
        x="sales",
        y="store_nbr",
        orientation="h",
        title="Top 10 tiendas con más ventas en productos en promoción",
        color="sales",
        color_continuous_scale="Oranges"
    )

    fig_top_promo.update_layout(
        yaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=order,
            title="Tienda"
        ),
        xaxis_title="Ventas",
        height=450
    )

    st.plotly_chart(fig_top_promo, use_container_width=True)

    # c) Estacionalidad
    st.markdown("### c) Estacionalidad de las ventas")

    # i) Día de la semana con más ventas (promedio)
    # Orden típico de días (por si viene como string)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if "day_of_week" in df_f.columns:
        dow_mean = df_f.groupby("day_of_week", as_index=False)["sales"].mean()
        if set(day_order).issuperset(set(dow_mean["day_of_week"].unique())):
            dow_mean["day_of_week"] = pd.Categorical(dow_mean["day_of_week"], categories=day_order, ordered=True)
            dow_mean = dow_mean.sort_values("day_of_week")
        fig_dow = px.bar(dow_mean, x="day_of_week", y="sales", title="Ventas medias por día de la semana")
        st.plotly_chart(fig_dow, use_container_width=True)
    else:
        st.info("No existe la columna day_of_week en el dataset filtrado.")

    # ii) Volumen medio por semana del año (promedio sobre años)
    week_mean = df_f.groupby("week", as_index=False)["sales"].mean().sort_values("week")
    fig_week = px.line(week_mean, x="week", y="sales", markers=True, title="Ventas medias por semana del año (promedio)")
    st.plotly_chart(fig_week, use_container_width=True)

    # iii) Volumen medio por mes (promedio sobre años)
    month_mean = df_f.groupby("month", as_index=False)["sales"].mean().sort_values("month")
    fig_month = px.line(month_mean, x="month", y="sales", markers=True, title="Ventas medias por mes (promedio)")
    st.plotly_chart(fig_month, use_container_width=True)

    """
    Se unen los puntos para mejorar la visualización y ver mejor la diferencia entre un dato y el siguiente.
    """
# ===========================
# PESTAÑA 2 — Por tienda
# ===========================
with tabs[1]:
    st.subheader("2) Análisis por tienda (store_nbr)")

    stores = sorted([int(x) for x in df_f["store_nbr"].dropna().unique()])
    store_sel = st.selectbox("Selecciona una tienda", options=stores)

    dstore = df_f[df_f["store_nbr"] == store_sel].copy()

    # a) Número total de ventas por año (suma sales)
    sales_year = dstore.groupby("year", as_index=False)["sales"].sum().sort_values("year")
    fig_sales_year = px.bar(sales_year, x="year", y="sales", title=f"Ventas totales por año — Tienda {store_sel}")

    # b) Número total de productos vendidos
    # Interpretación práctica: "sales" como unidades/ventas agregadas
    total_products_sold = float(dstore["sales"].sum())

    # c) Número total de productos vendidos en promoción
    promo_sold = float(dstore.loc[dstore["onpromotion"] > 0, "sales"].sum())

    m1, m2, m3 = st.columns(3)
    m1.metric("Ventas totales (suma sales)", f"{total_products_sold:,.2f}")
    m2.metric("Ventas en promoción (suma sales)", f"{promo_sold:,.2f}")
    m3.metric("Nº familias distintas vendidas", f"{int(dstore['family'].nunique()):,}")

    st.plotly_chart(fig_sales_year, use_container_width=True)

# ===========================
# PESTAÑA 3 — Por estado
# ===========================
with tabs[2]:
    st.subheader("3) Análisis por estado (state)")

    if "state" not in df_f.columns:
        st.error("No existe la columna 'state' en el dataset.")
    else:
        states = sorted([str(x) for x in df_f["state"].dropna().unique()])
        state_sel = st.selectbox("Selecciona un estado", options=states)

        dstate = df_f[df_f["state"] == state_sel].copy()
        dstate_tx = df_tx_f[df_tx_f["state"] == state_sel].copy()

        # a) Número total de transacciones por año (¡sin doble conteo!)
        tx_year = (
            dstate_tx.groupby("year", as_index=False)["transactions"]
            .sum()
            .sort_values("year")
        )
        fig_tx_year = px.bar(tx_year, x="year", y="transactions", title=f"Transacciones totales por año — {state_sel}")
        st.plotly_chart(fig_tx_year, use_container_width=True)

        # -----------------------------
        # b. Ranking de tiendas con más ventas (por estado)
        # -----------------------------
        """
        En el apartado siguiente, como el número de tiendas variará por estado, se necesita implementar un código que genere un gráfico visualmente atractivo independientemente del número de tiendas.
        Para ello, se pone un eje categórico y ordenado para evitar huecos ente tiendas, aunque sus números disten mucho uno del otro. Además, se elimina el uso de colores que se había implementado en la pestaña 1
        ya que, al haber tan pocas barras por gráfico (el número de tiendas por estado suelen rondar los 3-5), no es necesario diferenciar una de otra con colores.
        """
        state_store_sales = (dstate.groupby("store_nbr", as_index=False)["sales"].sum().sort_values("sales", ascending=False).head(10))

        # Forzamos categórico para que NO haya huecos
        state_store_sales["store_nbr"] = state_store_sales["store_nbr"].astype(str)

        # Orden explícito (ranking): menor->mayor para que el mayor quede arriba en horizontal
        order = state_store_sales.sort_values("sales")["store_nbr"].tolist()

        fig_state_store = px.bar(
            state_store_sales,
            x="sales",
            y="store_nbr",
            orientation="h",
            title=f"Ranking de tiendas con más ventas — {state_sel}",
            color_continuous_scale="Blues"
        )

        fig_state_store.update_layout(
            yaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=order,
                title="Tienda"
            ),
            xaxis_title="Ventas",
            height=420
        )
        st.plotly_chart(fig_state_store, use_container_width=True)

        # c) Producto más vendido (en el estado seleccionado)
        top_product_state = (
            dstate.groupby("family", as_index=False)["sales"]
            .sum()
            .sort_values("sales", ascending=False)
            .head(1)
        )

        if len(top_product_state) > 0:
            fam = top_product_state.iloc[0]["family"]
            val = float(top_product_state.iloc[0]["sales"])
            st.metric("Producto más vendido (en el estado)", f"{fam}", f"{val:,.2f} ventas")

            top10_products_state = (
                dstate.groupby("family", as_index=False)["sales"]
                .sum()
                .sort_values("sales", ascending=False)
                .head(10)
            )
            fig_top10_products_state = px.bar(
                top10_products_state,
                x="sales",
                y="family",
                orientation="h",
                title=f"Top 10 productos — {state_sel}",
            )
            fig_top10_products_state.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_top10_products_state, use_container_width=True)
        else:
            st.info("No hay datos suficientes para calcular el producto más vendido.")

# ===========================
# PESTAÑA 4 — Sorpresa
# ===========================
with tabs[3]:
    st.subheader("4) Insights extra para acelerar conclusiones")

    st.markdown("### 4.1 ¿Qué peso tienen las promociones?")
    total_sales = float(df_f["sales"].sum())
    promo_sales = float(df_f.loc[df_f["onpromotion"] > 0, "sales"].sum())
    share = (promo_sales / total_sales * 100) if total_sales > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas totales", f"{total_sales:,.2f}")
    c2.metric("Ventas en promoción", f"{promo_sales:,.2f}")
    c3.metric("% ventas promo", f"{share:,.2f}%")

    promo_comp = pd.DataFrame({
        "tipo": ["En promoción", "No promoción"],
        "sales": [promo_sales, total_sales - promo_sales],
    })
    fig_pie = px.pie(promo_comp, names="tipo", values="sales", title="Distribución de ventas: promoción vs no promoción")
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("### 4.2 Evolución temporal (ventas diarias + media móvil)")
    daily = df_f.groupby("date", as_index=False)["sales"].sum().sort_values("date")
    daily["rolling_14"] = daily["sales"].rolling(14, min_periods=1).mean()

    fig_daily = px.line(
    daily,
    x="date",
    y=["sales", "rolling_14"],
    title="Ventas diarias y media móvil (14 días)",
    color_discrete_map={
        "sales": "#184F76",
        "rolling_14": "red"      # rojo
    }
    )
    fig_daily.update_traces(selector=dict(name="rolling_14"), line=dict(width=4))

    
    st.plotly_chart(fig_daily, use_container_width=True)

    st.markdown("### 4.3 Ranking de estados por ventas (visión rápida)")
    if "state" in df_f.columns:
        state_rank = (
            df_f.groupby("state", as_index=False)["sales"]
            .sum()
            .sort_values("sales", ascending=False)
            .head(15)
        )
        fig_state_rank = px.bar(state_rank, x="sales", y="state", orientation="h", title="Top estados por ventas (Top 15)")
        fig_state_rank.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_state_rank, use_container_width=True)