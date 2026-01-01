# ContentPipeline: Autonomous SEO Content Engine 🚀

ContentPipeline is an enterprise-grade automation system that orchestrates the entire lifecycle of SEO publishing—from live data ingestion and AI-driven drafting to performance tracking via Google Search Console.

---

## 🏗️ System Architecture

This project is built on a **Distributed Microservices Architecture** to ensure high availability and scalability:

- **Frontend:** React.js SPA with Tailwind CSS for a high-performance editorial experience.
- **Backend:** FastAPI (Python) serving a RESTful API with asynchronous endpoints.
- **Task Orchestration:** Celery workers backed by **Redis** as a message broker to handle heavy LLM processing and scraping in the background.
- **Data Layer:** Redis-cached persistence for high-concurrency SEO analytics and content versioning.
- **Deployment:** Fully containerized using **Docker & Docker Compose**.

---

## ✨ Key Features

- **Autonomous Research Loop:** Scrapes live technical data and uses **GPT-4o** to generate factual, SEO-optimized content drafts.
- **Performance Feedback Loop:** Deep integration with the **Google Search Console API**. It automatically fetches Clicks and Impressions, caching them in Redis using a "Latest-Metric" pattern for instant dashboard reporting.
- **Human-in-the-loop Workflow:** A robust approval queue allowing for manual refinement and version history before one-click publishing.
- **Lite-Mode Optimization:** Intelligent backend data-stripping to ensure the dashboard remains responsive even with thousands of posts and heavy Base64 image data.

---

## 🛠️ Technical Stack

- **Languages:** Python 3.10+, JavaScript (React), PHP (WordPress Bridge).
- **Processing:** Celery, Redis, Scrapy, BeautifulSoup4.
- **AI/ML:** OpenAI API (GPT-4o / DALL-E 3).
- **APIs:** Google Search Console, WordPress REST API, XML-RPC.
- **Infrastructure:** Docker, Nginx, Linux.

---

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- OpenAI API Key
- Google Cloud Console Credentials (GSC API enabled)

### Installation
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/abdupa/ContentPipeline.git](https://github.com/abdupa/ContentPipeline.git)
   cd ContentPipeline
