
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_core.messages import HumanMessage, AIMessage
from app.database import Base, engine, get_db
from app import models, schemas
from app.agent import run_agent

from fastapi import UploadFile, File
from pypdf import PdfReader
import io
from app.rag import ingest_document
from fastapi.security import OAuth2PasswordBearer
from app.auth import hash_password, verify_password, create_access_token, decode_access_token


with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

# auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# On startup, create any tables that don't exist yet.
Base.metadata.create_all(bind=engine)
app = FastAPI(title="AskFlow API")
# Let the React dev server (port 5173) call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://askflow-1.onrender.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(401, "Account not found. Please log in again.")
    return user


@app.get("/health")
def health():
    return {"status": "ok"}
@app.get("/conversations", response_model=list[schemas.ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    ):
    return (db.query(models.Conversation)
       .filter(models.Conversation.user_id == current_user.id)
       .order_by(models.Conversation.created_at.desc())
       .all())

@app.get("/conversations/{cid}/messages",
         response_model=list[schemas.MessageOut])
def get_messages(
    cid: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    ):
    convo = db.get(models.Conversation, cid)
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo.messages


@app.patch("/conversations/{cid}", response_model=schemas.ConversationOut)
def rename_conversation(
    cid: int,
    payload: schemas.ConversationRename,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    convo = db.get(models.Conversation, cid)
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found")
    convo.title = payload.title.strip()[:200]
    db.commit()
    db.refresh(convo)
    return convo

@app.delete("/conversations/{cid}", status_code=204)
def delete_conversation(
    cid: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    convo = db.get(models.Conversation, cid)
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found")
    db.delete(convo)
    db.commit()

# @app.post("/chat", response_model=schemas.ChatResponse)
# def chat(req: schemas.ChatRequest, db: Session = Depends(get_db)):
#     # 1. Find the conversation, or create a new one.
#     if req.conversation_id:
#         convo = db.get(models.Conversation, req.conversation_id)
#         if not convo:
#             raise HTTPException(404, "Conversation not found")
#     else:
#         convo = models.Conversation(title=req.message[:40])
#         db.add(convo)
#         db.commit()
#         db.refresh(convo)         # reload to get the new id
#     # 2. Rebuild the prior chat history for the agent's memory.
#     history = []
#     for m in convo.messages:
#         if m.role == "user":
#             history.append(HumanMessage(content=m.content))
#         else:
#             history.append(AIMessage(content=m.content))

@app.post("/chat", response_model=schemas.ChatResponse)
# def chat(req: schemas.ChatRequest, db: Session = Depends(get_db)):
async def chat(req: schemas.ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user),):
    if req.conversation_id:
        convo = db.get(models.Conversation, req.conversation_id)
        if not convo:
            raise HTTPException(404, "Conversation not found")
    else:
        convo = models.Conversation(title=req.message[:40], user_id=current_user.id)
        db.add(convo)
        db.commit()
        db.refresh(convo)


    MAX_HISTORY_MESSAGES = 10
    history = []
    for m in convo.messages[-MAX_HISTORY_MESSAGES:]:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        else:
            history.append(AIMessage(content=m.content))
        
    total_chars = sum(len(m.content) for m in history)
    print(f"DEBUG: sending {len(history)} messages, {total_chars} total characters")

    db.add(models.Message(conversation_id=convo.id, role="user", content=req.message))
    db.commit()

    try:
        # reply = run_agent(req.message, history)
        reply = await run_agent(req.message, history)
    except Exception:
        reply = "Sorry, something went wrong on my end. Please try again."

    db.add(models.Message(conversation_id=convo.id, role="assistant", content=reply))
    db.commit()

    return schemas.ChatResponse(conversation_id=convo.id, reply=reply)


    # 3. Persist the new user message.
    db.add(models.Message(conversation_id=convo.id, role="user", content=req.message))
    db.commit()

    # 4. Ask the LangChain agent to produce a reply.
    reply = run_agent(req.message, history)

    # 5. Persist the assistant reply.
    db.add(models.Message(conversation_id=convo.id, role="assistant", content=reply))
    db.commit()

    # 6. Return JSON matching ChatResponse.
    return schemas.ChatResponse(conversation_id=convo.id, reply=reply)

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    raw = await file.read()

    if file.filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = raw.decode("utf-8", errors="ignore")

    if not text.strip():
        raise HTTPException(400, "Could not extract any readable text from this file.")

    doc_id = ingest_document(file.filename, text)
    return {"document_id": doc_id, "filename": file.filename}

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(401, "Account not found. Please log in again.")
    return user

@app.post("/auth/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(400, "That username is already taken. Please choose another.")
    user = models.User(username=payload.username, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return schemas.TokenResponse(access_token=token)

@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Incorrect username or password.")
    token = create_access_token(user.id)
    return schemas.TokenResponse(access_token=token)