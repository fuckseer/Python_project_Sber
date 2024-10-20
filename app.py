from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import pandas as pd
import matplotlib.pyplot as plt
import io

app = FastAPI()

# Указываем папку для статических файлов (CSS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем Jinja2 для рендеринга HTML
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    # Отображаем форму для загрузки файла
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/uploadfile/", response_class=HTMLResponse)
async def analyze_credit_products(request: Request, file: UploadFile = File(...)):
    # Чтение файла и анализ
    df = pd.read_excel(file.filename)
    df['Статус'] = df['Статус'].fillna('unknown')

    # Заполняем пропуски в столбце revenue нулями или любым другим значением
    df['Запрошенная сумма'] = df['Запрошенная сумма'].fillna(0)
    total_applications = df.shape[0]
    successful_applications = df[df['Статус'] == 'Одобрен'].shape[0]
    unsuccessful_applications = df[df['Статус'] == 'Отказ'].shape[0]
    total_revenue = df['Запрошенная сумма'].sum()
    average_revenue = df['Запрошенная сумма'].mean()

    # Генерация графика
    fig, ax = plt.subplots()
    ax.pie([successful_applications, unsuccessful_applications], labels=['Approved', 'Declined'], autopct='%1.1f%%')
    plt.title("Success Rate of Credit Applications")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plot_url = "/plot"

    # Передаем данные в шаблон для отображения
    return templates.TemplateResponse("results.html", {
        "request": request,
        "total_applications": total_applications,
        "successful_applications": successful_applications,
        "unsuccessful_applications": unsuccessful_applications,
        "total_revenue": total_revenue,
        "average_revenue": average_revenue,
        "plot_url": plot_url
    })


@app.get("/plot/")
async def get_plot():
    # Вернем график как изображение
    fig, ax = plt.subplots()
    ax.pie([70, 30], labels=['Одобрен', 'Отказ'], autopct='%1.1f%%')
    plt.title("Success Rate of Credit Applications")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
