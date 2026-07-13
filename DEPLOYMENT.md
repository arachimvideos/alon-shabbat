# פריסה לסביבת הדגמה

המערכת מחולקת לשני שירותים:

- `backend` - שרת FastAPI, בסיס נתונים SQLite וקבצי העלאות.
- `frontend` - ממשק React שנבנה לאתר סטטי.

## הגדרות נדרשות

בשרת ה-API:

```text
ALLOWED_ORIGINS=https://your-demo-site.example.com
DATA_DIR=/data
UPLOADS_DIR=/data/uploads
DB_PATH=/data/articles.db
```

באתר:

```text
VITE_API_BASE=https://your-api-service.example.com
```

ב-Docker של האתר ההגדרה הזו נטענת בזמן הרצה, כך שאפשר לשנות אותה גם אחרי בנייה מחדש של השירות.

## Render

קובץ `render.yaml` מגדיר שני שירותים:

- `aloney-shabbat-api`
- `aloney-shabbat-web`

אחרי יצירת השירותים, מעדכנים:

1. ב-`aloney-shabbat-web`: את `VITE_API_BASE` לכתובת ה-API.
2. ב-`aloney-shabbat-api`: את `ALLOWED_ORIGINS` לכתובת האתר.

לשרת ה-API מוגדר דיסק קבוע ב-`/data`, כדי שבסיס הנתונים והקבצים לא יימחקו בין הפעלות.

## בדיקה אחרי פריסה

פותחים:

```text
https://your-api-service.example.com/api/health
```

אם מתקבל:

```json
{"status":"ok"}
```

אפשר לפתוח את כתובת האתר ולבדוק יצירה, חיפוש והעלאת קובץ.
