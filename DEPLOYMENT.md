# פריסה חינמית עם אחסון קבוע

הפריסה מיועדת ל-Render Free עבור השרת והאתר, ול-Supabase Free עבור הנתונים והקבצים.

## Supabase

1. יוצרים פרויקט חינמי ב-Supabase.
2. מעתיקים את כתובת הפרויקט:
   `Project Settings -> API -> Project URL`
3. מעתיקים `service_role` key:
   `Project Settings -> API -> Project API keys`
4. מעתיקים את כתובת החיבור ל-Postgres:
   `Project Settings -> Database -> Connection string`

מומלץ להשתמש ב-connection string של pooler אם Supabase מציג אפשרות כזו.

## Render

הקובץ `render.yaml` מגדיר שני שירותים בתוכנית Free:

- `aloney-shabbat-api`
- `aloney-shabbat-web`

בזמן יצירת ה-Blueprint, ממלאים ב-Render את המשתנים הבאים עבור `aloney-shabbat-api`:

```text
ALLOWED_ORIGINS=https://your-web-service.onrender.com
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_BUCKET=alon-shabbat-uploads
```

עבור `aloney-shabbat-web` ממלאים:

```text
VITE_API_BASE=https://your-api-service.onrender.com
```

השרת יוצר את טבלאות ה-Postgres ואת ה-bucket ב-Supabase בעלייה הראשונה.

## מגבלות החינם

- Render Free יכול להירדם אחרי חוסר שימוש, ואז הבקשה הראשונה תהיה איטית.
- Supabase Free נשמר קבוע, אבל פרויקט חינמי עשוי להיות מושהה אחרי שבוע ללא פעילות.
- מגבלות Supabase Free בזמן כתיבת המסמך: 500MB למסד הנתונים ו-1GB לאחסון קבצים.

## בדיקה אחרי פריסה

פותחים:

```text
https://your-api-service.onrender.com/api/health
```

אם מתקבל:

```json
{"status":"ok"}
```

אפשר לפתוח את כתובת האתר ולבדוק יצירה, חיפוש והעלאת קובץ.
