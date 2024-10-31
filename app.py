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

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/uploadfile/")
async def upload_file(request: Request, file: UploadFile = File(...)):

    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Incorrect file format.Please load Excel file")

    global data

    try:
            contents = await file.read()
            data = pd.read_excel(io.BytesIO(contents))

            data['Дата'] = pd.to_datetime(data['Дата заявки'])

            products = list(data['Продукт'].unique())

            max_date_per_application = data.loc[data.groupby('ID заявки')['Дата заявки'].idxmax()]
            status_counts_by_product = max_date_per_application['Статус'].value_counts()

            total_applications_by_product = data.groupby('Продукт')['ID заявки'].count()
            approved_applications_by_product = data[data['Статус'] == 'Выдан'].groupby('Продукт')['ID заявки'].count()
            conversion_rate_by_product = (approved_applications_by_product / total_applications_by_product) * 100

            sum_by_day = data[data['Статус'] == 'Выдан'].groupby(['Дата заявки', 'Продукт'])['Запрошенная сумма'].sum().reset_index()

            fig3 = px.line(sum_by_day, x='Дата заявки', y='Запрошенная сумма', color='Продукт', title="Сумма выдач по дням и продуктам")
            fig1 = px.bar(status_counts_by_product, title='Статусы заявок')
            fig2 = px.pie(values=conversion_rate_by_product, names=conversion_rate_by_product.index, title='Конверсия по продуктам')

            graph_html1 = fig1.to_html(full_html=False)
            graph_html2 = fig2.to_html(full_html=False)
            graph_html3 = fig3.to_html(full_html=False)

            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "graph_html1": graph_html1,
                "graph_html2": graph_html2,
                "graph_html3": graph_html3,
                "products": products
            })
    except Exception as e:
        raise HTTPException (status_code=500, detail=f'Ошибка обработки файла: {str(e)}')

@app.get("/update_dashboard")
async def update_dashboard(product: str):
    global data
    if product == "all":
        filtered_data = data
    else:
        filtered_data = data[data['Продукт'] == product]

    max_date_per_application = filtered_data.loc[filtered_data.groupby('ID заявки')['Дата заявки'].idxmax()]
    status_counts_by_product = max_date_per_application['Статус'].value_counts()

    total_applications = filtered_data['ID заявки'].count()
    approved_applications = filtered_data[filtered_data['Статус'] == 'Выдан']['ID заявки'].count()
    conversion_rate = (approved_applications / total_applications) * 100 if total_applications > 0 else 0

    sum_by_day = filtered_data.groupby(['Дата заявки', 'Продукт'])['Запрошенная сумма'].sum().reset_index()

    fig1 = px.bar(status_counts_by_product, title=f'Статусы заявок для {product}')
    fig2 = px.pie(values=[conversion_rate, 100 - conversion_rate], names=['Выдан', 'Отказ'], title=f'Конверсия для {product}')
    fig3 = px.line(sum_by_day, x='Дата заявки', y='Запрошенная сумма', color='Продукт', title=f"Сумма выдач по дням для {product}")

    return {
        "statusGraph": fig1.to_json(),
        "conversionGraph": fig2.to_json(),
        "sumGraph":  fig3.to_json()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
