# Tag-o-matic

**Tag-o-matic** is a lightweight, responsive web application built for Flickr creators and archivists to inspect and perform bulk metadata updates across their photostream.

Built with **Flask**, **Tailwind CSS**, and **`requests_oauthlib`**, it communicates directly with Flickr's REST API using standard OAuth 1.0a authentication—eliminating session state issues and offering precise control over batch operations.

---

## Features

- **OAuth 1.0a Authentication:** Secure user authorization directly via Flickr without third-party wrapper library state bugs.
- **Aspect-Preserving Photostream Grid:** View photos in their native aspect ratio with letterboxed containers.
- **Custom Pagination & Sorting:** Choose page sizes (12, 24, 48, or 96 photos) and sort by date posted or date taken in ascending/descending order.
- **Batch Metadata Editing:**
  - **Add Tags:** Append multiple tags across selected photos simultaneously.
  - **Title Prefixing:** Add global prefixes to photo titles in bulk.
  - **Description Appending:** Add notes or extra text to existing descriptions.
- **Find & Replace Tags:** Scan selected photos for a specific tag and replace or remove it.
- **EXIF Dates & Geotagging:** Batch update photo `date_taken` timestamps and GPS latitude/longitude coordinates.
- **Interactive Metadata Inspector:** Inspect full photo metadata (ID, title, description, date taken, tags, and coordinates) without leaving the dashboard.
- **One-Click Batch Undo:** Revert previous metadata changes with a snapshot history stack.
- **Dynamic Variable Typography:** Styled using Adobe Typekit's variable font engine (`grtsk-vf`).

---

## Tech Stack

- **Backend:** Python 3, Flask, `requests-oauthlib`, `python-dotenv`
- **Frontend:** HTML5, JavaScript (ES6+), Tailwind CSS (CDN), Adobe Fonts (Typekit)
- **API Integration:** Flickr REST API (OAuth 1.0a)

---

## Project Structure

```
tag-o-matic/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── static/
│   └── fonts/
└── templates/
    └── index.html
```
---

## Getting Started

### 1. Prerequisites

- Python 3.9+
- A [Flickr App API Key & Secret](https://www.flickr.com/services/api/keys/apply/)

### 2. Installation

Clone the repository and navigate into the directory:
```
git clone https://github.com/nlr90004/tag-o-matic.git
cd tag-o-matic
```
Create and activate a virtual environment:
```
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
Install the dependencies:
```
pip install -r requirements.txt
```
### 3. Environment Configuration

Copy `.env.example` to create your local `.env` file:
```
cp .env.example .env
```
Open `.env` and fill in your credentials:
```
FLICKR_API_KEY=your_flickr_api_key
FLICKR_API_SECRET=your_flickr_api_secret
FLASK_SECRET_KEY=your_custom_flask_secret_key
```
*Note: Ensure your Flickr App settings specify `http://localhost:5000/auth/callback` as an authorized callback URL if required.*

### 4. Running the Application

Start the Flask development server:
```
python app.py
```
Open `http://localhost:5000` in your web browser and click **Connect to Flickr** to authenticate.