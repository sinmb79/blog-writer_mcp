# blog-writer-mcp

<p align="center">
  <img src="https://img.shields.io/badge/MCP-Streamable_HTTP-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/Python-3.11+-green?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" />
  <img src="https://img.shields.io/badge/Claude-Desktop-purple?style=flat-square" />
  <img src="https://img.shields.io/badge/ChatGPT-Developer_Mode-black?style=flat-square" />
</p>

<p align="center">
  <b>AI Blog Automation MCP Server</b><br/>
  <i>We find your voice in the things you love</i>
</p>

---

## The 4th Path: ⟨H⊕A⟩ ↦ Ω

Human (H) and AI (A), not as tools and users —
but as partners moving toward something better (Ω).

This is how 22B Labs builds. Everything free, everything open.
→ the4thpath.com

22B Labs | the4thpath.com  
MIT License

---

## What Is This?

`blog-writer-mcp` is a blog automation MCP server that lets Claude Desktop or ChatGPT drive a full writing pipeline through tool calls.

It combines:
- trend collection
- article writing with Creative DNA
- SEO and GEO optimization
- affiliate link insertion
- image generation
- publishing to Blogger and WordPress
- analytics and performance feedback

---

## Creative DNA

Most writing tools try to mimic your past writing. This project takes a different approach: it extracts tone, rhythm, values, and worldview from the things you love.

Favorite authors shape depth and cadence. Favorite books shape themes. Favorite films shape emotional scale. Favorite animation and aesthetics shape delivery.

The result is content that feels more like your sensibility than a generic AI output.

---

## Features

- `blog_get_trending`: collect ranked topics from the existing collector pipeline
- `blog_write_article`: generate a draft with optional Creative DNA style prefixing
- `blog_optimize_seo`: compute SEO and GEO suggestions from article HTML
- `blog_insert_affiliate_links`: insert context-aware affiliate links into content
- `blog_generate_image`: create or route image generation prompts
- `blog_publish`: publish to `blogger`, `wordpress`, or `both`
- `blog_get_analytics`: summarize performance data
- `blog_get_performance_feedback`: recommend next topics from historical results
- `blog_full_pipeline`: run the end-to-end automation flow

---

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- Claude Desktop or ChatGPT Plus/Pro
- A Blogger blog or WordPress site if you want publishing enabled

### Clone

```bash
git clone https://github.com/sinmb79/blog-writer_mcp.git
cd blog-writer_mcp
```

### Setup

```bash
# Windows
scripts\setup.bat

# Mac/Linux
pip install -e .
```

### Environment

```bash
copy .env.example .env
```

Fill in the values you need.

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
BLOG_MAIN_ID=

WP_URL=https://your-site.com
WP_USERNAME=your_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

For Blogger auth:

```bash
python scripts/get_token.py
```

---

## Running The MCP Server

```bash
python -m blogwriter_mcp.server
```

The server runs at:

```text
http://127.0.0.1:8766/mcp
```

---

## Claude Desktop Setup

Add this to your Claude Desktop config:

```json
{
  "mcpServers": {
    "blog_writer": {
      "command": "mcp-remote",
      "args": ["http://127.0.0.1:8766/mcp"]
    }
  }
}
```

Restart Claude Desktop after saving.

---

## ChatGPT Setup

ChatGPT cannot directly connect to `localhost`, so expose the server through a tunnel such as `ngrok`.

```bash
ngrok http 8766
```

Then register the generated HTTPS URL in ChatGPT Developer Mode as:

```text
https://your-tunnel-url/mcp
```

---

## Publishing Targets

### Blogger

The default `blog_publish` behavior stays on Blogger so existing workflows do not change.

### WordPress

WordPress publishing uses the REST API with Application Password authentication:

- post creation via `wp-json/wp/v2/posts`
- media upload via `wp-json/wp/v2/media`
- category and tag assignment
- draft save
- scheduled publish

### Both

Set `platform="both"` to publish to Blogger and WordPress in one MCP call.

---

## Example Prompts

```text
Set my creative DNA from Paulo Coelho, Zorba the Greek, Interstellar, and Ghibli.
```

```text
Pick one AI trend today and write a blog post in my DNA style.
```

```text
Publish this article to WordPress only.
```

```text
Publish this article to both Blogger and WordPress.
```

---

## Project Structure

```text
blog-writer-mcp/
├── bots/
│   ├── collector_bot.py
│   ├── writer_bot.py
│   ├── publisher_bot.py
│   ├── wp_publisher_bot.py
│   ├── image_bot.py
│   ├── analytics_bot.py
│   └── converters/
├── blogwriter_mcp/
│   ├── server.py
│   └── tools/
├── config/
├── templates/
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Release Verification

Run the local verification steps before publishing changes:

```bash
python -m pytest tests -v
python -m compileall blogwriter bots dashboard blog_engine_cli.py blog_runtime.py runtime_guard.py
cd dashboard/frontend && npm run build
```

---

## Contributing

Bug reports, feature requests, and pull requests are welcome.

```bash
git clone https://github.com/sinmb79/blog-writer_mcp.git
cd blog-writer_mcp
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Related Projects

- [sinmb79/blog-writer](https://github.com/sinmb79/blog-writer)
- [the4thpath.com](https://the4thpath.com)

---

## Author

**22B Labs** (sinmb79)

*The 4th Path: ⟨H⊕A⟩ ↦ Ω*

Human × AI → a better world.

*22B Labs | the4thpath.com*

---

<p align="center">
  <i>The 4th Path: ⟨H⊕A⟩ ↦ Ω</i><br/>
  <i>Human × AI → a better world.</i>
</p>
