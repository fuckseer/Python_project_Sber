from fastapi import FastAPI, UploadFile, File
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
    contents = await file.read()
    data = pd.read_excel(io.BytesIO(contents))

    total_applications = data['ID заявки'].count()

    approved_applications = data[data['Статус'] == 'Выдан']['ID заявки'].count()

    conversion_rate = (approved_applications / total_applications) * 100

    max_date_per_application = data.loc[data.groupby('ID заявки')['Дата заявки'].idxmax()]

    status_counts = max_date_per_application['Статус'].value_counts()

    fig = px.pie(names=status_counts.index, values=status_counts.values, title='Заявки по статусам')
    graph_html = fig.to_html(full_html=False)

    return templates.TemplateResponse("results.html", {
        "request": request,
        "total_applications": total_applications,
        "approved_applications": approved_applications,
        "conversion_rate": round(conversion_rate, 2),
        "status_counts": status_counts.to_dict(),
        "graph_html": graph_html
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
