CONFLICT_TEST_LINE
# Resource Booking Management System

**FastAPI** REST API for managing organizational **resources** (rooms, equipment, etc.) and **bookings** against those resources. Data is persisted as **JSON files** under `app/data/`.

## Features

- **Resources**: create, list, get by id, update (partial), delete.
- **Bookings**: create, list, get by id, update (partial), delete.
- **Validation**: `capacity` must be at least **1**; a booking can only reference an existing **`resource_id`** (on create and when changing `resource_id` on update).
- **IDs**: server-generated UUID strings for new resources and bookings.
- **HTTP semantics**: `201` for successful creates, `204` for successful deletes, `404` for missing entities, `400` for business-rule violations (e.g. unknown resource on booking).


## How to run

1. Create and activate a virtual environment (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the API from the **project root** (the directory that contains `app/`):

   ```bash
   uvicorn app.main:app --reload
   ```

4. Open the interactive docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), or call `GET http://127.0.0.1:8000/` for a short JSON overview.

Initial data files `app/data/resources.json` and `app/data/bookings.json` are empty arrays `[]` and are filled as you use the API.

## Demo data (optional, manual)

To load **10 sample resources** and **5 sample bookings**, run from the **project root** with your virtual environment activated:

```bash
python -m app.seed
```

The script **does not** run on server startup. It removes any existing rows whose ids start with `demo-seed-` (and bookings pointing at those resources), then inserts fresh demo records. Your own data (e.g. UUID ids from the API) is left unchanged.
