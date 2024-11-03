from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import pandas as pd
import plotly.express as px
from starlette.requests import Request
from fastapi.templating import Jinja2Templates
import io

from starlette.staticfiles import StaticFiles

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount('/static', StaticFiles(directory='static'), name='static')

data = None

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """
    Отображает главную страницу с формой для загрузки файла.

    :param request: Request - HTTP-запрос.
    :return: HTML-страница.
    """
    return templates.TemplateResponse("index.html", {"request": request})


def validate_file(file: UploadFile):
    """
    Проверяет, что загруженный файл имеет правильный формат Excel (.xls или .xlsx).

    :param file: UploadFile - Загруженный файл от пользователя.
    :raises HTTPException: Если формат файла неверен, выбрасывается исключение HTTP 400.
    """
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Incorrect file format. Please upload an Excel file.")


async def load_data(file: UploadFile) -> pd.DataFrame:
    """
    Загружает и читает данные из Excel-файла, преобразуя их в DataFrame.

    :param file: UploadFile - Загруженный Excel-файл.
    :return: DataFrame с прочитанными данными.
    :raises HTTPException: Если файл не удается прочитать, выбрасывается исключение HTTP 500.
    """
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        df['Дата'] = pd.to_datetime(df['Дата заявки'])
        return df
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


def prepare_data(df: pd.DataFrame):
    """
    Подготавливает обобщенные данные по продуктам, такие как список продуктов,
    подсчет количества продуктов и распределение статусов заявок.

    :param df: DataFrame - DataFrame с данными из Excel-файла.
    :return: Словарь, содержащий уникальные продукты, количество каждого продукта и распределение статусов.
    """
    products = list(df['Продукт'].unique())
    products_counts = df['Продукт'].value_counts()
    max_date_per_application = df.loc[df.groupby('ID заявки')['Дата заявки'].idxmax()]
    status_counts_by_product = max_date_per_application['Статус'].value_counts()

    return {
        "products": products,
        "products_counts": products_counts,
        "status_counts_by_product": status_counts_by_product
    }


def create_graphs(df: pd.DataFrame, product: str = "all"):
    """
    Создает интерактивные графики Plotly для отображения различных показателей по продуктам.

    :param df: DataFrame - DataFrame с данными из Excel-файла.
    :param product: str - Название продукта для фильтрации данных; если "all", фильтрация не применяется.
    :return: Словарь с графиками в формате HTML.
    """
    filtered_data = df if product == "all" else df[df['Продукт'] == product]
    sum_by_day = filtered_data[filtered_data['Статус'] == 'Выдан'].groupby(['Дата заявки', 'Продукт'])[
        'Запрошенная сумма'].sum().reset_index()
    rate_analysis = filtered_data.groupby(['Дата заявки', 'Продукт'])['Ставка'].agg(
        ['mean', 'min', 'max']).reset_index()
    rate_analysis.columns = ['Дата заявки', 'Продукт', 'Средняя ставка', 'Минимальная ставка', 'Максимальная ставка']

    total_applications = filtered_data['ID заявки'].count()
    approved_applications = filtered_data[filtered_data['Статус'] == 'Выдан']['ID заявки'].count()
    conversion_rate = (approved_applications / total_applications) * 100

    fig1 = px.bar(prepare_data(filtered_data)['status_counts_by_product'], title=f"Статусы заявок для {product}")
    fig2 = px.pie(values=[conversion_rate, 100 - conversion_rate], title=f'Конверсия для {product}')
    fig3 = px.line(sum_by_day, x='Дата заявки', y='Запрошенная сумма', color='Продукт',
                   title=f"Сумма выдач по дням для {product}")
    fig4 = px.line(rate_analysis, x='Дата заявки', y='Средняя ставка', color='Продукт', title=f'Распределение ставок {product}')

    return {
        "statusGraph": fig1,
        "conversionGraph": fig2,
        "sumGraph": fig3,
        "normGraph": fig4
    }


@app.post("/uploadfile/")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Обрабатывает загруженный файл, проверяет его формат, загружает данные и отображает дашборд с графиками.

    :param request: Request - HTTP-запрос.
    :param file: UploadFile - Загруженный файл от пользователя.
    :return: HTML-страница дашборда с графиками.
    :raises HTTPException: Если формат файла неверен или при обработке файла возникает ошибка.
    """
    global data
    validate_file(file)
    data = await load_data(file)

    product_data = prepare_data(data)
    graph_data = create_graphs(data)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "graph_html1": graph_data["statusGraph"].to_html(full_html=False),
        "graph_html2": graph_data["conversionGraph"].to_html(full_html=False),
        "graph_html3": graph_data["sumGraph"].to_html(full_html=False),
        "graph_html4": graph_data["normGraph"].to_html(full_html=False),
        "products": product_data["products"]
    })


@app.get("/update_dashboard")
async def update_dashboard(product: str):
    """
        Обновляет графики на дашборде при выборе определенного продукта.

        :param product: str - Название продукта для фильтрации данных; если "all", фильтрация не применяется.
        :return: Словарь с обновленными графиками в формате HTML.
        :raises HTTPException: Если данные еще не загружены.
    """
    global data
    if data is None:
        raise HTTPException(status_code=400, detail="No data available. Please upload a file first.")

    graph_data = create_graphs(data, product)
    return {
        "statusGraph": graph_data["statusGraph"].to_json(),
        "conversionGraph": graph_data["conversionGraph"].to_json(),
        "sumGraph": graph_data["sumGraph"].to_json(),
        "normGraph": graph_data["normGraph"].to_json()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
