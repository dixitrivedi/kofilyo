# Kofilyo: Sales & Expense Tracker

A Streamlit app for a hot & cold beverage business. It records daily cups sold and daily
raw-item spend, then turns them into weekly and monthly analysis.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Without Google Sheets set up, data is stored locally in `data/beverage.db` (SQLite).

## Login

The app asks for a password, set in `.streamlit/secrets.toml`:
```toml
[auth]
password = "your password"
```
Change it any time by editing that line (and the same line in Streamlit Cloud's Secrets). Online, the
app refuses to open if no password is set. Five wrong tries lock the login for a minute. Reloading the
browser page logs you out.

## Backups before deleting

*Delete all data* and *Load demo data* (Menu and prices) first copy the `sales` and `expenses` tabs
into new tabs such as `backup 2026-11-19 14.05 sales`. If the copy fails, nothing is deleted.
To undo: open the backup tab, select all, copy, and paste over the `sales` (or `expenses`) tab from
cell A1. Delete old backup tabs whenever you no longer need them.

## Store your data in Google Sheets (needed for Streamlit Cloud)

Streamlit Cloud wipes its disk on every restart, so online the app keeps its data in a Google Sheet
with three tabs: `products`, `sales` and `expenses`. You can open the sheet any time to look at the
numbers. Avoid editing it by hand while the app is in use; the app re-reads the sheet every 5 minutes.

**1. Make a Google "service account" (a robot login the app uses)**
1. Go to <https://console.cloud.google.com>, sign in, and create a project (for example `Kofilyo`).
2. *APIs & Services → Library*: enable **Google Sheets API** and **Google Drive API**.
3. *APIs & Services → Credentials → Create credentials → Service account*. Name it `kofilyo`, press
   *Done* (no roles needed).
4. Open the new service account → *Keys → Add key → Create new key → JSON*. A `.json` file downloads.
   Keep it private: anyone with it can edit your sheet.

**2. Make the sheet**
1. Create an empty Google Sheet (<https://sheets.new>) and name it `Kofilyo data`.
2. Press *Share*, paste the service account's email (it ends in `iam.gserviceaccount.com`, and is in
   the JSON file as `client_email`), choose **Editor**, and send.

**3. Connect the app on your laptop**
```bash
pip install -r requirements.txt
python make_secrets.py ~/Downloads/<your-key>.json "https://docs.google.com/spreadsheets/d/<id>/edit"
python copy_to_sheets.py      # one time: copies your existing local data into the sheet
streamlit run app.py
```
The bottom of *Menu and prices* now says "Your data is stored in: Google Sheet: Kofilyo data".

**4. Put it on Streamlit Cloud**
1. Push this folder to a GitHub repository (private is best). `.streamlit/secrets.toml`, `*.json` key
   files and `data/` are in `.gitignore`, so your key and local data are not uploaded.
2. On <https://share.streamlit.io> → *Create app*, pick the repository and set the main file to `app.py`
   (or `beverage_app/app.py` if this folder sits inside a bigger repository).
3. *Advanced settings → Secrets*: paste the whole contents of your `.streamlit/secrets.toml`. Deploy.
   It must include the `[auth]` password section, or the app stays locked.
4. In the app's sharing settings, make it private and invite only the people who should see your numbers.

## Pages

| Page | What it does |
|---|---|
| Today | Today's takings vs yesterday, cups, stock spend, today's share of running costs, profit, 14-day chart, bestsellers |
| Record sales | Tap − / + (or type) cups per drink, then how you were paid (cash / UPI / card, with a "Rest is cash" button and a check against the day's total); Save sales |
| Record purchases | Add stock purchases, edit (pencil) or delete (bin) them |
| Running costs | Rent, salaries, electricity… per month. A whole-month cost is shared evenly over its days; a one-day cost lands on its date. "Copy last month's monthly costs" saves re-typing |
| Weekly / Monthly report | Sales, cups, stock spend, running costs, true profit and margin vs the previous period; day-by-day chart; payment split; bestsellers and money makers; spending; 12-period trend; tables and CSV |
| Cost per cup | A recipe per drink (e.g. 150 ml milk, 5 g tea, 1 cup). Prices come from your purchases: the average paid over the last 90 days, or the latest purchase. Shows cost, profit and margin per cup |
| Menu and prices | Rename drinks, change prices, switch drinks off, delete, add drinks, CSV backups, demo data, reset |

The look is "Espresso bar". Switch between **Dark** and **Light** at the top of the sidebar;
the choice is kept in the URL (`?theme=light`) so a bookmark opens in your theme.

For a week or month still in progress, comparisons use the same number of days from the previous period.

## Customise

`theme.py` holds the brand name (`BRAND_NAME`), currency (`CURRENCY`) and both colour palettes (`THEMES`).
`.streamlit/config.toml` sets the Streamlit theme colours.
