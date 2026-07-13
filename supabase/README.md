# Supabase setup

Run `migrations/001_init.sql` in the Supabase SQL Editor:

1. Open the Supabase project.
2. Go to `SQL Editor`.
3. Paste the contents of `supabase/migrations/001_init.sql`.
4. Click `Run`.

The migration creates:

- `parashot`
- `tags`
- `articles`
- `article_tags`

Quick verification query:

```sql
SELECT 'parashot' AS table_name, COUNT(*) FROM public.parashot
UNION ALL
SELECT 'tags', COUNT(*) FROM public.tags
UNION ALL
SELECT 'articles', COUNT(*) FROM public.articles
UNION ALL
SELECT 'article_tags', COUNT(*) FROM public.article_tags;
```

Expected result after the initial migration:

- `parashot`: 54
- `tags`: 0
- `articles`: 0
- `article_tags`: 0

## Import local data

The local content currently lives in `backend/data/articles.db`. After running the
initial migration, import it into Supabase from PowerShell:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
cd ..

$env:DATABASE_URL = "postgresql://..."
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "..."
$env:SUPABASE_BUCKET = "alon-shabbat-uploads"

python .\scripts\migrate_sqlite_to_supabase.py --clear
```

What the importer does:

- copies `parashot`, `tags`, `articles`, and `article_tags` from SQLite to Supabase
- keeps the original IDs so tag links and article links stay valid
- uploads local article/image files to Supabase Storage when the Supabase storage env vars are set
- rewrites uploaded file paths to `supabase://bucket/object-name`
- resets Postgres identity sequences after the import

For a count-only check that does not connect to Supabase:

```powershell
python .\scripts\migrate_sqlite_to_supabase.py --dry-run
```

Use `--skip-files` only if you want to copy database rows without uploading local
files to Supabase Storage.

Do not save Supabase passwords, `DATABASE_URL`, or service role keys in this repository.
