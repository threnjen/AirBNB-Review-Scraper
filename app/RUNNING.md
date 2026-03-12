# Running the ADR Prediction Web App

## Prerequisites

- Dependencies installed (`pipenv install`)
- Two-stage residual model trained and saved to `ml/model/residual/`
  - Run `pipenv run python ml/train_2_level.py` if the model doesn't exist yet
  - Required files: `stage1_model.joblib`, `stage1_feature_columns.json`, `stage2_model.joblib`, `stage2_feature_columns.json`

## Starting the app

### Quickest way (via Makefile)

```bash
make run-app
```

### Manually

```bash
pipenv run flask --app app/app run --debug
```

Both commands start the server at **http://127.0.0.1:5000** by default.

## Using the form

1. **Property Details** — enter the 4 base fields:
   - Capacity (guests), Bedrooms, Beds, Bathrooms
2. **Location** — enter the property's latitude and longitude
   - These are used to compute the distance to the configured point of interest (`poi_lat` / `poi_long` in `config.json`)
3. **Amenities** — check any amenities the property has
4. Click **Predict ADR** — the predicted average daily rate appears at the top of the page

The form preserves all entered values after a prediction so you can tweak inputs and re-predict.

## Changing the port or host

```bash
pipenv run flask --app app/app run --debug --port 8080
pipenv run flask --app app/app run --debug --host 0.0.0.0  # accessible on the network
```

## Production (no debug mode)

```bash
pipenv run flask --app app/app run
```

Or with a production WSGI server:

```bash
pipenv run gunicorn "app.app:app"
```

> **Note:** The model is loaded once at startup. Restarting the server is required to pick up a newly retrained model.
