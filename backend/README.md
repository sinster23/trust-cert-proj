Yes, exactly. The backend README should be a **small developer quick-start**, not an architecture document. M1 can then append/update it when authentication is added.

I'd use this:

```markdown
# Credence Backend

Backend API for the Credence project, built with **FastAPI** and **MongoDB**.

## Setup

### 1. Create and activate virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file using `.env.example` as a reference.

Do not commit `.env` or any secrets.

### 4. Run the backend

From the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Current Progress

### FastAPI Foundation
- Shared FastAPI application created in `app/main.py`.

### M4 — Database Foundation ✅

The initial MongoDB database layer is implemented under:

```text
app/database/
```

It currently provides:

- MongoDB connection management
- User model
- User repository
- User creation and lookup
- Email normalization
- Duplicate-email protection
- Database error handling

M4 uses **PyMongo Async**.

Other modules should use the database/repository layer rather than accessing MongoDB directly.

### Next

**M1 — Authentication**

Google Workspace authentication and Credence JWT-based API authentication will be added next.

---

## Development Notes

- Use the existing shared FastAPI application. Do not create a separate FastAPI server for individual modules.
- Keep required Python dependencies updated in `requirements.txt`.
- Keep `.env` out of Git.
- Update this README when adding a major backend feature or changing the setup process.
```

This is much more appropriate for `backend/README.md`.

Then **M1's README remains the detailed specification** we made earlier, while `backend/README.md` simply tells someone:

> How do I run the backend, and what's currently implemented?

Once M1 finishes, they can change:

```text
### Next

M1 — Authentication
```

to something like:

```text
### M1 — Authentication ✅

Google Workspace authentication and Credence JWT authentication implemented.
```

and add the next module under it.