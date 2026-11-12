# QPyServe dashboard starter

A responsive dashboard using **ordinary HTML/CSS/JavaScript**, FastAPI and the
QPyServe Data Bridge. No Node.js, charting library, or hand-written data route.

## Run

Install the optional Data Bridge dependencies once:

    python -m pip install "qpyserve[data]>=0.7.0"

Then start the generated app:

    python main.py

Open http://localhost:1111 and edit data/sample.csv. The dashboard checks for
file changes every five seconds and reloads a bounded page when it changes.

To start from an existing CSV file, create the starter with:

    qpyserve new my-dashboard --template dashboard --data /path/to/file.csv --public-data

The explicit --public-data flag acknowledges that the copied CSV is **publicly
queryable** when this application is deployed. Never use this starter with
credentials, private records, or sensitive data until you have replaced
public=True with appropriate FastAPI authorization and row-level restrictions.

## Customize

- Edit frontend/index.html: the frontend is plain HTML, CSS and JavaScript.
- Edit data/sample.csv: use the original column headers and values of your data.
- Edit main.py: add ordinary FastAPI routes or protect the Data Bridge.
- The metric selector detects numeric columns; the search and table use the
  first 500 rows returned, and the chart previews at most 24 filtered rows.
  **KPI values represent the loaded page, not the full source dataset.**
- Change the query limit or add server-side aggregations for larger datasets.
  Do not interpret a bounded page's totals as totals for the entire dataset.

Read the Data Bridge guide at
https://github.com/austinwin/qpyserve/blob/v0.7.0/docs/DATA_BRIDGE.md .
The generated dashboard is a starter, not a production analytics platform.
