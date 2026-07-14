import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  ArrowRight,
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  CalendarDays,
  Edit3,
  FileDown,
  Image as ImageIcon,
  Italic,
  LayoutGrid,
  List,
  ListOrdered,
  Plus,
  Search,
  SlidersHorizontal,
  Underline,
  X,
} from "lucide-react";
import {
  createArticle,
  fileUrl,
  getArticle,
  imageUrl,
  listArticles,
  listParashot,
  listTags,
  updateArticle,
} from "./api";
import "./styles.css";

const emptyFilters = {
  q: "",
  parasha_id: "",
  tags: [],
  tag_match: "any",
  publication_from: "",
  publication_to: "",
  uploaded_from: "",
  uploaded_to: "",
  sort_by: "uploaded_at",
  sort_dir: "desc",
};

const initialVisibleCount = 36;

function App() {
  const [parashot, setParashot] = useState([]);
  const [tags, setTags] = useState([]);
  const [articles, setArticles] = useState([]);
  const [filters, setFilters] = useState(emptyFilters);
  const [viewMode, setViewMode] = useState("cards");
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingArticle, setEditingArticle] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [visibleCount, setVisibleCount] = useState(initialVisibleCount);
  const [message, setMessage] = useState("");

  useEffect(() => {
    Promise.all([listParashot(), listTags()])
      .then(([parashaData, tagData]) => {
        setParashot(parashaData);
        setTags(tagData);
      })
      .catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setVisibleCount(initialVisibleCount);
    listArticles(filters)
      .then(setArticles)
      .catch((error) => setMessage(error.message))
      .finally(() => setIsLoading(false));
  }, [filters]);

  const selectedTagNames = useMemo(() => {
    return tags.filter((tag) => filters.tags.includes(String(tag.id))).map((tag) => tag.name);
  }, [filters.tags, tags]);

  const featuredArticles = articles.slice(0, 5);
  const visibleArticles = articles.slice(0, visibleCount);
  const hasMoreArticles = visibleCount < articles.length;

  function updateFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
  }

  function toggleTag(id) {
    const value = String(id);
    setFilters((current) => {
      const exists = current.tags.includes(value);
      return {
        ...current,
        tags: exists ? current.tags.filter((tagId) => tagId !== value) : [...current.tags, value],
      };
    });
  }

  async function openArticle(id) {
    try {
      const article = await getArticle(id);
      setSelectedArticle(article);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function handleSaved(savedArticle, mode) {
    setIsFormOpen(false);
    setEditingArticle(null);
    const [articleData, tagData] = await Promise.all([listArticles(filters), listTags()]);
    setArticles(articleData);
    setTags(tagData);
    if (selectedArticle && savedArticle?.id === selectedArticle.id) {
      setSelectedArticle(savedArticle);
    }
    setMessage(mode === "edit" ? "המאמר עודכן בהצלחה" : "המאמר נשמר בהצלחה");
  }

  function openCreateForm() {
    setEditingArticle(null);
    setIsFormOpen(true);
  }

  function openEditForm(article) {
    setEditingArticle(article);
    setIsFormOpen(true);
  }

  if (selectedArticle) {
    return (
      <>
        <ArticlePage
          article={selectedArticle}
          onBack={() => setSelectedArticle(null)}
          onEdit={() => openEditForm(selectedArticle)}
          message={message}
          onDismissMessage={() => setMessage("")}
        />
        {isFormOpen && (
          <ArticleForm
            article={editingArticle}
            parashot={parashot}
            allTags={tags}
            onClose={() => {
              setIsFormOpen(false);
              setEditingArticle(null);
            }}
            onSaved={handleSaved}
            onError={(error) => setMessage(error.message)}
          />
        )}
      </>
    );
  }

  return (
    <main className="app-shell">
      <header className="site-header">
        <div className="brand-mark" aria-label="ארכיון עלוני שבת">
          <span>ש</span>
          <strong>עלוני שבת</strong>
        </div>
        <nav className="header-nav" aria-label="ניווט ראשי">
          <a href="#articles">מאמרים</a>
          <a href="#search">חיפוש</a>
          <a href="#tags">תגיות</a>
        </nav>
        <button className="primary-button" onClick={openCreateForm}>
          <Plus size={18} />
          הוספת מאמר
        </button>
      </header>

      <Notice message={message} onDismiss={() => setMessage("")} />

      <section className="hero-section">
        <div className="hero-copy">
          <p className="eyebrow">ארכיון מאמרים</p>
          <h1>מאגר מאמרים לפרשת השבוע</h1>
          <p>
            המאמרים התפרסמו בעלון לשבת של ערכים.
            <br />
            מאת <strong className="hero-author">הרב דניאל נשיא</strong>
          </p>
          <div className="hero-actions">
            <button className="primary-button" onClick={openCreateForm}>
              <Plus size={18} />
              מאמר חדש
            </button>
            <a className="ghost-link" href="#search">
              לחיפוש מתקדם
              <ArrowLeft size={18} />
            </a>
          </div>
        </div>

        <FeaturedMosaic articles={featuredArticles} onOpen={openArticle} />
      </section>

      <section id="search" className="toolbar" aria-label="חיפוש וסינון">
        <div className="toolbar-title">
          <div>
            <p className="eyebrow">חיפוש וסינון</p>
          </div>
          <SlidersHorizontal size={22} />
        </div>

        <label className="search-field">
          <Search size={18} />
          <input
            value={filters.q}
            onChange={(event) => updateFilter("q", event.target.value)}
            placeholder="חיפוש בכותרת, כותרת משנה, מספר גיליון, פרשה, תגיות, מחבר, שם קובץ או תוכן"
          />
        </label>

        <div className="filter-grid">
          <Field label="פרשה">
            <select
              value={filters.parasha_id}
              onChange={(event) => updateFilter("parasha_id", event.target.value)}
            >
              <option value="">כל הפרשות</option>
              {parashot.map((parasha) => (
                <option key={parasha.id} value={parasha.id}>
                  {parasha.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="מתאריך פרסום">
            <input
              type="date"
              value={filters.publication_from}
              onChange={(event) => updateFilter("publication_from", event.target.value)}
            />
          </Field>
          <Field label="עד תאריך פרסום">
            <input
              type="date"
              value={filters.publication_to}
              onChange={(event) => updateFilter("publication_to", event.target.value)}
            />
          </Field>
          <Field label="מתאריך העלאה">
            <input
              type="date"
              value={filters.uploaded_from}
              onChange={(event) => updateFilter("uploaded_from", event.target.value)}
            />
          </Field>
          <Field label="עד תאריך העלאה">
            <input
              type="date"
              value={filters.uploaded_to}
              onChange={(event) => updateFilter("uploaded_to", event.target.value)}
            />
          </Field>
          <Field label="מיון">
            <select
              value={`${filters.sort_by}:${filters.sort_dir}`}
              onChange={(event) => {
                const [sort_by, sort_dir] = event.target.value.split(":");
                setFilters((current) => ({ ...current, sort_by, sort_dir }));
              }}
            >
              <option value="uploaded_at:desc">הועלה לאחרונה</option>
              <option value="uploaded_at:asc">הועלה ראשון</option>
              <option value="publication_date:desc">פרסום חדש לישן</option>
              <option value="publication_date:asc">פרסום ישן לחדש</option>
              <option value="parasha:asc">פרשה</option>
              <option value="title:asc">כותרת</option>
            </select>
          </Field>
        </div>

        <div id="tags" className="tag-panel">
          <div className="tag-panel-header">
            <span>תגיות</span>
            <select
              value={filters.tag_match}
              onChange={(event) => updateFilter("tag_match", event.target.value)}
            >
              <option value="any">לפחות אחת</option>
              <option value="all">כל התגיות</option>
            </select>
          </div>
          <div className="tag-list">
            {tags.length === 0 && <span className="muted">אין תגיות עדיין</span>}
            {tags.map((tag) => (
              <button
                key={tag.id}
                className={filters.tags.includes(String(tag.id)) ? "tag active" : "tag"}
                onClick={() => toggleTag(tag.id)}
              >
                {tag.name}
              </button>
            ))}
          </div>
          {selectedTagNames.length > 0 && (
            <p className="selected-tags">נבחרו: {selectedTagNames.join(", ")}</p>
          )}
        </div>

        <div className="view-row">
          <button className="ghost-button" onClick={() => setFilters(emptyFilters)}>
            ניקוי סינון
          </button>
          <div className="segmented" aria-label="בחירת תצוגה">
            <button
              className={viewMode === "cards" ? "active" : ""}
              onClick={() => setViewMode("cards")}
              title="תצוגת כרטיסים"
            >
              <LayoutGrid size={18} />
            </button>
            <button
              className={viewMode === "table" ? "active" : ""}
              onClick={() => setViewMode("table")}
              title="תצוגת טבלה"
            >
              <List size={18} />
            </button>
          </div>
        </div>
      </section>

      <section id="articles" className="results-header">
        <div>
          <p className="eyebrow">תוצאות</p>
          <h2>{articles.length} מאמרים</h2>
        </div>
        {isLoading && <span>טוען...</span>}
      </section>

      {viewMode === "cards" ? (
        <ArticleCards articles={visibleArticles} onOpen={openArticle} />
      ) : (
        <ArticleTable articles={visibleArticles} onOpen={openArticle} />
      )}

      {hasMoreArticles && (
        <div className="load-more-row">
          <button className="secondary-button" onClick={() => setVisibleCount((count) => count + initialVisibleCount)}>
            טען עוד מאמרים
          </button>
        </div>
      )}

      {isFormOpen && (
        <ArticleForm
          article={editingArticle}
          parashot={parashot}
          allTags={tags}
          onClose={() => {
            setIsFormOpen(false);
            setEditingArticle(null);
          }}
          onSaved={handleSaved}
          onError={(error) => setMessage(error.message)}
        />
      )}
    </main>
  );
}

function FeaturedMosaic({ articles, onOpen }) {
  if (articles.length === 0) {
    return (
      <div className="mosaic empty-mosaic">
        <ImageIcon size={42} />
        <p>כשתעלו מאמרים עם תמונות, הם יופיעו כאן כקיר תוכן מעוצב.</p>
      </div>
    );
  }

  return (
    <div className="mosaic" aria-label="מאמרים נבחרים">
      {articles.map((article, index) => (
        <button
          key={article.id}
          className={`mosaic-card mosaic-card-${index + 1}`}
          onClick={() => onOpen(article.id)}
        >
          <ArticleImage article={article} />
          <span>{article.parasha_name}</span>
          <strong>{article.title}</strong>
          {article.subtitle && <small>{article.subtitle}</small>}
        </button>
      ))}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Notice({ message, onDismiss }) {
  if (!message) {
    return null;
  }

  return (
    <div className="notice">
      <span>{message}</span>
      <button aria-label="סגירת הודעה" onClick={onDismiss}>
        <X size={16} />
      </button>
    </div>
  );
}

function ArticleImage({ article, className = "" }) {
  if (!article.image_original_filename) {
    return (
      <div className={`article-image placeholder-image ${className}`}>
        <ImageIcon size={26} />
      </div>
    );
  }

  return (
    <img
      className={`article-image ${className}`}
      src={imageUrl(article.id)}
      alt=""
      loading="lazy"
    />
  );
}

function ArticleCards({ articles, onOpen }) {
  if (articles.length === 0) {
    return <EmptyState />;
  }
  return (
    <section className="cards-grid">
      {articles.map((article) => (
        <article className="article-card" key={article.id}>
          <ArticleImage article={article} />
          <div className="article-card-main">
            <div className="article-card-kicker">
              <p className="parasha">{article.parasha_name}</p>
              {article.issue_number && (
                <span className="issue-badge">גיליון {article.issue_number}</span>
              )}
            </div>
            <h3>{article.title}</h3>
            {article.subtitle && <p className="article-subtitle">{article.subtitle}</p>}
            <p className="summary">
              {plainText(article.body_text || article.extracted_text) || "אין תוכן להצגה כרגע"}
            </p>
          </div>
          <ArticleMeta article={article} showIssue={false} />
          <MatchSources article={article} />
          <button className="secondary-button" onClick={() => onOpen(article.id)}>
            פתיחת מאמר
            <ArrowLeft size={16} />
          </button>
        </article>
      ))}
    </section>
  );
}

function ArticleTable({ articles, onOpen }) {
  if (articles.length === 0) {
    return <EmptyState />;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>כותרת</th>
            <th>מספר גיליון</th>
            <th>פרשה</th>
            <th>מחבר</th>
            <th>פרסום</th>
            <th>תגיות</th>
            <th>התאמה</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {articles.map((article) => (
            <tr key={article.id}>
              <td>
                <strong>{article.title}</strong>
                {article.subtitle && <span className="table-subtitle">{article.subtitle}</span>}
              </td>
              <td>{article.issue_number || "-"}</td>
              <td>{article.parasha_name}</td>
              <td>{article.author_name || "-"}</td>
              <td>{formatDate(article.publication_date)}</td>
              <td>{article.tags.map((tag) => tag.name).join(", ") || "-"}</td>
              <td>{article.match_sources?.join(", ") || "-"}</td>
              <td>
                <button className="link-button" onClick={() => onOpen(article.id)}>
                  פתיחה
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArticleMeta({ article, showIssue = true }) {
  return (
    <div className="meta">
      {article.author_name && <span>{article.author_name}</span>}
      {showIssue && article.issue_number && <span>גיליון {article.issue_number}</span>}
      {article.publication_date && (
        <span>
          <CalendarDays size={14} />
          {formatDate(article.publication_date)}
        </span>
      )}
      {article.tags.map((tag) => (
        <span key={tag.id}>{tag.name}</span>
      ))}
    </div>
  );
}

function MatchSources({ article }) {
  if (!article.match_sources || article.match_sources.length === 0) {
    return null;
  }
  return <p className="matches">התאמה: {article.match_sources.join(", ")}</p>;
}

function EmptyState() {
  return (
    <section className="empty-state">
      <h2>אין עדיין מאמרים להצגה</h2>
      <p>אפשר להוסיף מאמר חדש או לנקות את הסינון הקיים.</p>
    </section>
  );
}

function ArticlePage({ article, onBack, onEdit, message, onDismissMessage }) {
  return (
    <main className="app-shell article-page">
      <div className="article-page-actions">
        <button className="back-button" onClick={onBack}>
          <ArrowRight size={18} />
          חזרה לרשימת החיפוש
        </button>
        <button className="ghost-button" onClick={onEdit}>
          <Edit3 size={18} />
          עריכת מאמר
        </button>
      </div>
      <Notice message={message} onDismiss={onDismissMessage} />
      <article className="article-full">
        <ArticleImage article={article} className="article-hero-image" />
        <div className="article-full-content">
          <p className="parasha">{article.parasha_name}</p>
          <h1>{article.title}</h1>
          {article.subtitle && <p className="article-page-subtitle">{article.subtitle}</p>}
          <ArticleMeta article={article} />
          <dl className="details">
            <div>
              <dt>מספר גיליון</dt>
              <dd>{article.issue_number || "-"}</dd>
            </div>
            <div>
              <dt>תאריך העלאה</dt>
              <dd>{formatDateTime(article.uploaded_at)}</dd>
            </div>
            <div>
              <dt>סטטוס</dt>
              <dd>{article.status}</dd>
            </div>
          </dl>
          <div className="article-body">
            <RichArticleBody content={article.body_text || article.extracted_text} />
          </div>
          {article.original_filename && (
            <a className="download-link" href={fileUrl(article.id)}>
              <FileDown size={18} />
              פתיחת הקובץ המקורי: {article.original_filename}
            </a>
          )}
        </div>
      </article>
    </main>
  );
}

function ArticleForm({ article, parashot, allTags = [], onClose, onSaved, onError }) {
  const [isSaving, setIsSaving] = useState(false);
  const isEdit = Boolean(article);

  async function submit(event) {
    event.preventDefault();
    setIsSaving(true);
    const form = event.currentTarget;
    const formData = new FormData(form);
    try {
      const savedArticle = isEdit
        ? await updateArticle(article.id, formData)
        : await createArticle(formData);
      form.reset();
      await onSaved(savedArticle, isEdit ? "edit" : "create");
    } catch (error) {
      onError(error);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="modal" onSubmit={submit}>
        <div className="modal-header">
          <h2>{isEdit ? "עריכת מאמר" : "הוספת מאמר"}</h2>
          <button type="button" aria-label="סגירה" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <Field label="כותרת">
          <input name="title" required defaultValue={article?.title || ""} />
        </Field>
        <Field label="כותרת משנה">
          <input name="subtitle" defaultValue={article?.subtitle || ""} />
        </Field>
        <Field label="מספר גיליון">
          <input name="issue_number" inputMode="numeric" defaultValue={article?.issue_number || ""} />
        </Field>
        <Field label="פרשה">
          <select name="parasha_id" required defaultValue={article?.parasha_id || ""}>
            <option value="" disabled>
              בחירת פרשה
            </option>
            {parashot.map((parasha) => (
              <option key={parasha.id} value={parasha.id}>
                {parasha.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="מחבר">
          <input name="author_name" defaultValue={article?.author_name || ""} />
        </Field>
        <Field label="תאריך פרסום">
          <input name="publication_date" type="date" defaultValue={article?.publication_date || ""} />
        </Field>
        <Field label="תגיות">
          <TagSelector articleTags={article?.tags || []} allTags={allTags} />
        </Field>
        <Field label="תמונת מאמר">
          <input name="image" type="file" accept="image/*" />
          {isEdit && article.image_original_filename && (
            <span className="field-note">תמונה קיימת: {article.image_original_filename}</span>
          )}
        </Field>
        <div className="field">
          <span>טקסט מלא</span>
          <RichTextEditor name="body_text" defaultValue={article?.body_text || ""} />
        </div>
        <Field label="קובץ מצורף">
          <input name="file" type="file" accept=".doc,.docx,.pdf,.txt,.md" />
          {isEdit && article.original_filename && (
            <span className="field-note">קובץ קיים: {article.original_filename}</span>
          )}
        </Field>
        <div className="modal-actions">
          <button type="button" className="ghost-button" onClick={onClose}>
            ביטול
          </button>
          <button type="submit" className="primary-button" disabled={isSaving}>
            {isSaving ? "שומר..." : isEdit ? "שמירת שינויים" : "שמירת מאמר"}
          </button>
        </div>
      </form>
    </div>
  );
}

function TagSelector({ articleTags, allTags }) {
  const articleTagKey = articleTags.map((tag) => tag.name).join("\u0000");
  const [selectedNames, setSelectedNames] = useState(() => articleTags.map((tag) => tag.name));
  const [newTags, setNewTags] = useState("");

  useEffect(() => {
    setSelectedNames(articleTags.map((tag) => tag.name));
    setNewTags("");
  }, [articleTagKey]);

  const payloadTags = useMemo(() => {
    return uniqueTagNames([...selectedNames, ...splitTagNames(newTags)]);
  }, [newTags, selectedNames]);

  function toggleTag(name) {
    setSelectedNames((current) => {
      const exists = current.some((tagName) => sameTagName(tagName, name));
      return exists
        ? current.filter((tagName) => !sameTagName(tagName, name))
        : [...current, name];
    });
  }

  function removeSelected(name) {
    setSelectedNames((current) => current.filter((tagName) => !sameTagName(tagName, name)));
  }

  return (
    <div className="tag-selector">
      <input type="hidden" name="tags" value={payloadTags.join(", ")} readOnly />
      <div className="tag-selector-list" aria-label="בחירת תגיות קיימות">
        {allTags.length === 0 && <span className="muted">אין תגיות קיימות עדיין</span>}
        {allTags.map((tag) => {
          const isSelected = selectedNames.some((name) => sameTagName(name, tag.name));
          return (
            <button
              key={tag.id}
              type="button"
              className={isSelected ? "tag active" : "tag"}
              onClick={() => toggleTag(tag.name)}
            >
              {tag.name}
            </button>
          );
        })}
      </div>
      <input
        value={newTags}
        onChange={(event) => setNewTags(event.target.value)}
        placeholder="הוספת תגיות חדשות, מופרדות בפסיקים"
      />
      {payloadTags.length > 0 && (
        <div className="tag-selector-selected" aria-label="תגיות שישמרו">
          {payloadTags.map((name) => (
            <span key={name} className="selected-tag-pill">
              {name}
              {selectedNames.some((selectedName) => sameTagName(selectedName, name)) && (
                <button type="button" aria-label={`הסרת התגית ${name}`} onClick={() => removeSelected(name)}>
                  <X size={14} />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function splitTagNames(value = "") {
  return value
    .split(/[,;\n]+/)
    .map((name) => name.trim())
    .filter(Boolean);
}

function uniqueTagNames(names) {
  const seen = new Set();
  const unique = [];
  names.forEach((name) => {
    const key = normalizeTagNameKey(name);
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(name);
    }
  });
  return unique;
}

function sameTagName(first, second) {
  return normalizeTagNameKey(first) === normalizeTagNameKey(second);
}

function normalizeTagNameKey(name) {
  return name.trim().toLocaleLowerCase();
}

const paragraphFormats = [
  { value: "p", label: "טקסט רגיל" },
  { value: "h1", label: "כותרת 1" },
  { value: "h2", label: "כותרת 2" },
];

const editorFonts = [
  { value: "Heebo", label: "Heebo" },
  { value: "Arial", label: "Arial" },
  { value: "David", label: "David" },
  { value: "Times New Roman", label: "Times" },
];

const editorColors = ["#241a16", "#7a1f26", "#9a6a1d", "#1f5f74", "#2f6f45"];
const editorVersion = "2026-07-13 12:40";

function RichTextEditor({ name, defaultValue }) {
  const editorRef = useRef(null);
  const hiddenInputRef = useRef(null);
  const selectionRef = useRef(null);
  const initialHtml = useMemo(() => toEditableHtml(defaultValue), [defaultValue]);

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = initialHtml;
    }
    if (hiddenInputRef.current) {
      hiddenInputRef.current.value = initialHtml;
    }
  }, [initialHtml]);

  function syncEditor() {
    if (hiddenInputRef.current) {
      hiddenInputRef.current.value = sanitizeRichText(editorRef.current?.innerHTML || "");
    }
    saveSelection();
  }

  function saveSelection() {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0) {
      return;
    }
    const range = selection.getRangeAt(0);
    if (editor.contains(range.commonAncestorContainer)) {
      selectionRef.current = range.cloneRange();
    }
  }

  function restoreSelection() {
    const selection = window.getSelection();
    const range = selectionRef.current;
    if (!selection || !range) {
      return;
    }
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function runCommand(command, commandValue = null) {
    editorRef.current?.focus();
    restoreSelection();
    document.execCommand(command, false, commandValue);
    saveSelection();
    syncEditor();
  }

  function handlePaste(event) {
    event.preventDefault();
    const text = event.clipboardData.getData("text/plain");
    restoreSelection();
    document.execCommand("insertText", false, text);
    saveSelection();
    syncEditor();
  }

  function keepEditorSelection(event) {
    event.preventDefault();
    saveSelection();
  }

  return (
    <div className="rich-editor">
      <input ref={hiddenInputRef} type="hidden" name={name} defaultValue={initialHtml} />
      <div className="editor-toolbar" aria-label="כלי עריכת טקסט">
        <select defaultValue="p" onMouseDown={saveSelection} onFocus={saveSelection} onChange={(event) => runCommand("formatBlock", event.target.value)} title="סגנון פסקה">
          {paragraphFormats.map((format) => (
            <option key={format.value} value={format.value}>
              {format.label}
            </option>
          ))}
        </select>
        <select defaultValue={editorFonts[0].value} onMouseDown={saveSelection} onFocus={saveSelection} onChange={(event) => runCommand("fontName", event.target.value)} title="בחירת פונט">
          {editorFonts.map((font) => (
            <option key={font.value} value={font.value}>
              {font.label}
            </option>
          ))}
        </select>
        <div className="editor-button-group">
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("bold")} title="מודגש">
            <Bold size={17} />
          </button>
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("italic")} title="נטוי">
            <Italic size={17} />
          </button>
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("underline")} title="קו תחתון">
            <Underline size={17} />
          </button>
        </div>
        <div className="editor-button-group">
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("insertUnorderedList")} title="רשימה">
            <List size={17} />
          </button>
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("insertOrderedList")} title="רשימה ממוספרת">
            <ListOrdered size={17} />
          </button>
        </div>
        <div className="editor-button-group">
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("justifyRight")} title="יישור ימינה">
            <AlignRight size={17} />
          </button>
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("justifyCenter")} title="מרכוז">
            <AlignCenter size={17} />
          </button>
          <button type="button" onMouseDown={keepEditorSelection} onClick={() => runCommand("justifyLeft")} title="יישור שמאלה">
            <AlignLeft size={17} />
          </button>
        </div>
        <div className="color-swatches" aria-label="צבע טקסט">
          {editorColors.map((color) => (
            <button
              key={color}
              type="button"
              onMouseDown={keepEditorSelection}
              onClick={() => runCommand("foreColor", color)}
              title="צבע טקסט"
              style={{ "--swatch-color": color }}
            />
          ))}
        </div>
        <span className="editor-version">גרסת עורך {editorVersion}</span>
        <button type="button" className="editor-clear" onMouseDown={keepEditorSelection} onClick={() => runCommand("removeFormat")}>
          ניקוי עיצוב
        </button>
      </div>
      <div
        ref={editorRef}
        className="editor-surface"
        contentEditable
        dir="rtl"
        role="textbox"
        aria-multiline="true"
        data-placeholder="הקלידו את טקסט המאמר..."
        suppressContentEditableWarning
        onInput={syncEditor}
        onBlur={syncEditor}
        onKeyUp={saveSelection}
        onMouseUp={saveSelection}
        onSelect={saveSelection}
        onPaste={handlePaste}
      />
    </div>
  );
}

function RichArticleBody({ content }) {
  const value = content || "לא נשמר טקסט למאמר";
  if (hasHtml(value)) {
    return <div dangerouslySetInnerHTML={{ __html: sanitizeRichText(value) }} />;
  }
  return value.split("\n").map((line, index) => <p key={index}>{line || "\u00A0"}</p>);
}

function hasHtml(value = "") {
  return /<\/?[a-z][\s\S]*>/i.test(value);
}

function toEditableHtml(value = "") {
  if (!value) {
    return "";
  }
  if (hasHtml(value)) {
    return sanitizeRichText(value);
  }
  return value
    .split("\n")
    .map((line) => `<p>${escapeHtml(line) || "<br>"}</p>`)
    .join("");
}

function plainText(value = "") {
  if (!value) {
    return "";
  }
  if (!hasHtml(value)) {
    return value;
  }
  const element = document.createElement("div");
  element.innerHTML = sanitizeRichText(value);
  return element.textContent || "";
}

function sanitizeRichText(html = "") {
  const template = document.createElement("template");
  template.innerHTML = html;
  const allowedTags = new Set([
    "A",
    "B",
    "BLOCKQUOTE",
    "BR",
    "DIV",
    "EM",
    "FONT",
    "H1",
    "H2",
    "H3",
    "I",
    "LI",
    "OL",
    "P",
    "SPAN",
    "STRONG",
    "U",
    "UL",
  ]);
  const allowedStyles = new Set([
    "color",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-align",
    "text-decoration-line",
    "text-decoration",
  ]);

  template.content.querySelectorAll("*").forEach((node) => {
    if (!allowedTags.has(node.tagName)) {
      node.replaceWith(...node.childNodes);
      return;
    }
    [...node.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (name.startsWith("on")) {
        node.removeAttribute(attribute.name);
      } else if (name === "style") {
        const safeStyles = [...node.style]
          .filter((property) => allowedStyles.has(property))
          .map((property) => `${property}: ${node.style.getPropertyValue(property)}`)
          .join("; ");
        if (safeStyles) {
          node.setAttribute("style", safeStyles);
        } else {
          node.removeAttribute("style");
        }
      } else if (!(node.tagName === "FONT" && ["color", "face", "size"].includes(name))) {
        node.removeAttribute(attribute.name);
      }
    });
  });

  return template.innerHTML.trim();
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("he-IL").format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("he-IL", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

createRoot(document.getElementById("root")).render(<App />);


