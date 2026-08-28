# IntegrationOneS

Сервис сверки остатков между базой 1С "Управление торговлей" и одной или несколькими налоговыми базами 1С. Приложение получает выгрузки по HTTP, нормализует строки, находит расхождения и формирует Excel-отчет `.xlsx`.

## Функциональность

- Web-форма для запуска сверки за произвольный период.
- Загрузка списка складов из 1С через endpoint `/warehouses`.
- Фильтрация сверки по выбранным складам.
- Получение данных из базы управления торговлей и налоговых баз через HTTP GET.
- Поддержка базовой HTTP-авторизации для подключений к 1С.
- Нормализация русских и англоязычных имен полей выгрузки.
- Нормализация сумм с пробелами, неразрывными пробелами и запятой в качестве десятичного разделителя.
- Поиск отсутствующих, лишних и дублирующих документов.
- Поиск расхождений в суммах дебета, кредита и текущего сальдо с настраиваемым допуском.
- Формирование Excel-отчета с типом расхождения и рекомендацией.
- Unit-тесты для нормализации, валидации запроса, клиента 1С, сверки и генерации отчета.

## Структура проекта

```text
.
├── app/
│   ├── config.py           # загрузка .env и настроек подключений
│   ├── models.py           # dataclass-модели строк и расхождений
│   ├── normalization.py    # нормализация ответа 1С
│   ├── onec_client.py      # HTTP-клиент для 1С
│   ├── reconciliation.py   # логика сверки
│   └── reporting.py        # генерация XLSX-отчета
├── tests/
│   └── test_reconciliation.py
├── index.html              # web-форма
├── main.py                 # FastAPI-приложение и API-роуты
├── requirements.txt
├── .env.example
└── README.md
```

## Требования

- Windows 10/11 или совместимое окружение с PowerShell.
- Python 3.14+.
- Доступ к HTTP-эндпоинтам 1С.
- Технические учетные записи 1С с правами на чтение.

Зависимости проекта:

```text
fastapi==0.141.1
uvicorn==0.52.1
requests==2.34.2
pydantic==2.13.4
```

## Установка

Откройте PowerShell в корне проекта:

```powershell
cd C:\Users\a.luchinin\PycharmProjects\IntegrationOneS
```

Создайте и активируйте виртуальное окружение:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Установите зависимости:

```powershell
python -m pip install -r requirements.txt
```

## Настройка

Создайте локальный файл настроек из примера:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Заполните реальные параметры подключений:

```env
ONEC_TRADE_NAME=Управление торговлей
ONEC_TRADE_URL=https://example.local/trade/remainders
ONEC_TRADE_WAREHOUSES_URL=https://example.local/trade/warehouses
ONEC_TRADE_USERNAME=readonly_user
ONEC_TRADE_PASSWORD=readonly_password
ONEC_TAX_BASES_JSON=[{"name":"Налоговая база","url":"https://example.local/tax/remainders","username":"readonly_user","password":"readonly_password"}]
ONEC_HTTP_TIMEOUT_SECONDS=15
ONEC_AMOUNT_TOLERANCE=0.01
```

Параметры:

- `ONEC_TRADE_NAME` - отображаемое имя базы управления торговлей.
- `ONEC_TRADE_URL` - endpoint выгрузки строк из базы управления торговлей.
- `ONEC_TRADE_WAREHOUSES_URL` - endpoint получения списка складов.
- `ONEC_TRADE_USERNAME` и `ONEC_TRADE_PASSWORD` - учетные данные для базы управления торговлей.
- `ONEC_TAX_BASES_JSON` - JSON-массив налоговых баз. Для каждой базы указываются `name`, `url`, опционально `username`, `password`, `warehouses_url`.
- `ONEC_HTTP_TIMEOUT_SECONDS` - timeout HTTP-запросов к 1С.
- `ONEC_AMOUNT_TOLERANCE` - допустимое расхождение сумм при сравнении.

## Формат обмена с 1С

Для выгрузки строк сервис отправляет запрос:

```text
GET <url>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

Если выбраны склады, они передаются повторяющимся query-параметром:

```text
GET <url>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&warehouse=Основной склад&warehouse=Склад 2
```

Endpoint складов вызывается без параметров:

```text
GET <ONEC_TRADE_WAREHOUSES_URL>
```

Список складов может быть массивом строк:

```json
["Основной склад", "Склад 2"]
```

Также поддерживается объект с ключом `warehouses`, `data`, `items`, `rows` или `result`, если значение ключа является массивом. Элементы массива могут быть строками или объектами с полем `name`, `Название`, `название`, `Склад`, `склад` или `warehouse`.

Выгрузка строк должна быть списком объектов или объектом с ключом `data`, `items`, `rows` или `result`.

Поддерживаемые поля строки:

| Каноническое поле | Алиасы |
| --- | --- |
| `period` | `period`, `Период`, `период` |
| `document` | `document`, `Документ`, `документ` |
| `debit_analytics` | `debit_analytics`, `Аналитика Дт`, `аналитика дт`, `Analytic Dt` |
| `credit_analytics` | `credit_analytics`, `Аналитика Кт`, `аналитика кт`, `Analytic Kt` |
| `debit` | `debit`, `Дебет`, `дебет` |
| `credit` | `credit`, `Кредит`, `кредит` |
| `balance` | `balance`, `Текущее сальдо`, `текущее сальдо` |

Если `period` отсутствует, сервис подставляет период запроса в формате `DD.MM.YYYY-DD.MM.YYYY`.

## Запуск

Запустите backend и web-форму одним FastAPI-сервером:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Откройте форму:

```text
http://127.0.0.1:8000/
```

Проверка доступности:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing
```

Если порт `8000` занят, используйте другой:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8010
```

## API

### `GET /`

Возвращает HTML-форму запуска сверки.

### `GET /health`

Возвращает статус приложения:

```json
{"status":"ok"}
```

### `GET /warehouses`

Загружает список складов из `ONEC_TRADE_WAREHOUSES_URL`.

Пример ответа:

```json
{
  "warehouses": ["Основной склад", "Склад 2"]
}
```

### `POST /reconcile`

Запускает сверку и возвращает Excel-файл.

Тело запроса:

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "warehouses": ["Основной склад", "Склад 2"]
}
```

`warehouses` можно не передавать или передать пустым массивом, тогда сверка выполняется без фильтра по складам.

Пример ручного запроса:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/reconcile" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"start_date":"2024-01-01","end_date":"2024-01-31","warehouses":["Основной склад"]}' `
  -OutFile ".\reconciliation_2024-01-01_2024-01-31.xlsx"
```

## Отчет

При наличии расхождений отчет содержит колонки:

- `Период`
- `База`
- `Документ`
- `Аналитика Дт`
- `Аналитика Кт`
- `Дебет`
- `Кредит`
- `Текущее сальдо`
- `Тип расхождения`
- `Рекомендация`

Если расхождений нет, формируется `.xlsx` с одной строкой `Расхождения не обнаружены`.

Типы расхождений:

- `Отсутствие документа в налоговой базе`
- `Лишний документ в налоговой базе`
- `Дублирующий документ`
- `Различия в данных документа`
- `Невозможность однозначного сопоставления`

## Тесты

Запуск unit-тестов:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Проверка импорта приложения:

```powershell
.\.venv\Scripts\python.exe -c "from main import app; print(app.title)"
```

Ожидаемый вывод:

```text
Сверка остатков 1С
```

## Типовые ошибки

### `Unexpected token '<', "<!doctype "... is not valid JSON`

Браузер получил HTML вместо JSON или Excel-файла. Проверьте, что форма открыта через `http://127.0.0.1:8000/`, а не напрямую как `file://.../index.html`.

### `Не задан обязательный параметр конфигурации ONEC_TRADE_URL`

Не создан `.env` или не заполнен URL базы управления торговлей.

### `ONEC_TAX_BASES_JSON должен быть валидным JSON`

В переменной `ONEC_TAX_BASES_JSON` нарушен JSON-синтаксис. Проверьте кавычки, запятые и квадратные скобки массива.

### `Не удалось получить данные из базы ...`

1С-эндпоинт недоступен, вернул ошибку, не принимает параметры `start_date`/`end_date` или указаны неверные учетные данные.

### `422 Unprocessable Entity`

Тело запроса к `/reconcile` не соответствует модели. Проверьте формат дат `YYYY-MM-DD`; `end_date` должен быть больше или равен `start_date`.

## Лицензия

Лицензия в репозитории не указана. Перед публикацией или передачей проекта добавьте файл `LICENSE` и обновите этот раздел.

## Контакты

- GitHub: [cursedemokid/IntegrationOneSProject](https://github.com/cursedemokid/IntegrationOneSProject)
