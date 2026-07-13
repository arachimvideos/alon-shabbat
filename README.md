# מערכת מאמרים לעלון פרשת שבוע

מערכת מקומית לניהול, חיפוש וצפייה במאמרים שבועיים. הגרסה הראשונה בנויה לפי האיפיון: React בצד הלקוח, FastAPI בצד השרת, SQLite לאחסון, ותיקיית uploads לשמירת קבצים מצורפים.

## מבנה הפרויקט

- `backend` - שרת API, בסיס נתונים, העלאת קבצים וחיפוש.
- `frontend` - ממשק משתמש בעברית, RTL, רספונסיבי.
- `uploads` - קבצים מקוריים שמועלים למאמרים.

## הפעלה

במחשב הזה אפשר להשתמש בקבצי ההפעלה שבתיקיית `scripts`:

```powershell
.\scripts\start-backend.ps1
```

ובחלון נוסף:

```powershell
.\scripts\start-frontend.ps1
```

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
pnpm install
pnpm dev
```

הממשק יפנה כברירת מחדל אל `http://localhost:8000`.
