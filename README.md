# Logseq Processor

Process articles with AI-powered metadata extraction using GitHub Actions.

## 🎯 How It Works

**Simple 3-step workflow:**

1. **Copy files** → `01_inbox/` folder
2. **Push to GitHub** → `git push`
3. **Pull results** → `git pull` (check `03_success/` and `04_failed/`)

That's it! No complex setup, no background scripts.

## 📁 The Kanban Folders

```
01_inbox/        ← You put .md files here
   ↓ (GitHub Action processes automatically)
02_processing/   ← Files being processed (visible progress)
   ↓
03_success/      ← ✓ Finished articles (ready to use!)
04_failed/       ← ✗ Files with errors (see filename for reason)
```

## 🚀 Quick Start

### Step 1: Add Your Files

```bash
# Copy article files to the inbox folder
cp ~/Nextcloud/Notes/article.md logseq-processor/01_inbox/
cp ~/Nextcloud/Notes/another.md logseq-processor/01_inbox/
```

### Step 2: Push to GitHub

```bash
cd logseq-processor
git add 01_inbox/
git commit -m "Add articles for processing"
git push origin main
```

### Step 3: Wait & Pull

GitHub Action automatically processes your files (~10-30 minutes per article).

```bash
# Check results
git pull
ls 03_success/        # Successfully processed articles
ls 04_failed/         # Any errors (check filename for reason)
```

### Step 4: Use Results

Copy files from `03_success/` to your Logseq library.

## ✅ What Gets Generated

**Input file:** `article.md`

**Success:** `03_success/article-Article-Title-20260330-153645.md`
```markdown
title:: Article Title
tags:: technology, ai
url:: https://original-url.com
summary:: Generated summary of the article...

Full article content here...
```

**Error:** `04_failed/article_ERROR_http_blocked_403.md`
- Shows the error reason in filename
- Original file included (for your reference)

## 🔧 Error Codes

| Error | Meaning | What to do |
|-------|---------|-----------|
| `ERROR_http_blocked_403` | Server rejected request | Wait, try different URL |
| `ERROR_http_blocked_429` | Rate limited | Try again later |
| `ERROR_empty_content` | No readable content | Check URL, try different source |
| `ERROR_parse_error` | HTML parsing failed | Check URL format |
| `ERROR_timeout_120s` | Processing took too long | Very long article? Try shorter one |
| `ERROR_url_invalid` | Invalid URL format | Check URL spelling |

## 🔄 Retrying Failed Files

If a file fails, you can retry it:

**Simple retry** (fixes the original issue):
```bash
# Fix the issue first (wait a minute, try different URL, etc)
mv 04_failed/article_ERROR_http_blocked_403.md 01_inbox/article.md
git add .
git commit -m "Retry: article.md"
git push
```

**Force retry** (ignores cache):
```bash
# Forces reprocessing even if seen before
mv 04_failed/article_ERROR_http_blocked_403.md 01_inbox/article--force.md
git add .
git commit -m "Force retry: article.md"
git push
```

## 📊 What Happens Behind the Scenes

1. **File detection**: Action detects files in `01_inbox/`
2. **Move to processing**: Files moved to `02_processing/` (shows progress)
3. **Extract content**: Downloads article from URL
4. **Extract text**: Uses web parsing to get readable content
5. **Generate metadata**: Ollama LLM creates title, tags, summary
6. **Create markdown**: Formats as Logseq-ready markdown
7. **Move to result folder**: 
   - Success → `03_success/` ✓
   - Error → `04_failed/` ✗
8. **Commit & push**: Results saved to GitHub

## ⏱️ Processing Time

- **First run**: 10-20 minutes (model download + processing)
- **Subsequent runs**: 10-15 minutes per article
- **Factors**: Content size, complexity, Ollama model performance

## 🐛 Troubleshooting

**Files not being processed?**
- Check GitHub Actions is enabled in repo settings
- Verify files are in `01_inbox/` folder
- Check workflow run status in Actions tab

**Files in `02_processing/` stuck?**
- Action may have timed out
- Check GitHub Actions logs for errors
- Try pushing a dummy change to trigger action again

**Same file keeps failing?**
- Read the error code in filename
- Fix the issue (website down, bad URL, etc)
- Re-upload with `--force` flag

**Processing is very slow?**
- First run downloads Ollama model (~5GB) - this takes time
- Very long articles take longer
- Model caching speeds up subsequent articles

## 📦 Dependencies

- Python 3.11+
- GitHub Actions (free, included)
- Ollama in Docker (runs in GitHub)
- No local setup needed!

## 🎯 Features

✅ **Automatic URL extraction** from markdown files  
✅ **LLM metadata generation** (title, tags, summary)  
✅ **Error handling** with detailed error codes  
✅ **Transparent progress** in folder structure  
✅ **Easy retry** for failed files  
✅ **Logseq ready** output  
✅ **No local Ollama needed** (runs in GitHub)

## 📝 Notes

- Files in `02_processing/` keep history (not deleted)
- Filenames include timestamp (for sorting)
- Original files moved out of `01_inbox/` after processing
- Git history shows all processing activity

## 🚀 That's All!

Simple, transparent, no complex setup. Just:
1. Copy files to `01_inbox/`
2. Push to GitHub
3. Pull results when done

Questions? Check the folder structure - it shows everything! 📁

---

**Version**: Kanban Workflow (Simplified)  
**Last Updated**: March 30, 2026
