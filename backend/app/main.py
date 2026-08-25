from datetime import date, datetime, timedelta
from typing import Any
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .curriculum import LESSON_CONTENT, UNITS, find_lesson, public_card
from .database import Base, engine, get_db
from .models import ExerciseAttempt, Learner, LessonProgress, LessonSession

app = FastAPI(title="PageCraft API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)

class StartBody(BaseModel):
    learner_id: str

class AnswerBody(BaseModel):
    answer: Any

def learner(db: Session, learner_id: str) -> Learner:
    value = db.get(Learner, learner_id)
    if not value:
        value = Learner(id=learner_id)
        db.add(value)
        db.commit()
        db.refresh(value)
    return value

def progress_map(db: Session, learner_id: str):
    rows = db.scalars(select(LessonProgress).where(LessonProgress.learner_id == learner_id)).all()
    return {row.lesson_slug: row for row in rows}

def lesson_unlocked(ui: int, li: int, progress: dict) -> bool:
    if ui == 0 and li == 0:
        return True
    if ui == 0:
        previous = UNITS[ui][4][li - 1][0]
        return progress.get(previous) is not None and progress[previous].status in ("completed", "mastered")
    previous_unit_last = UNITS[ui - 1][4][-1][0]
    return progress.get(previous_unit_last) is not None and progress[previous_unit_last].status in ("completed", "mastered")

def course_payload(db: Session, learner_id: str):
    person = learner(db, learner_id)
    progress = progress_map(db, learner_id)
    units = []
    next_lesson = None
    for ui, (slug, title, description, icon, lessons) in enumerate(UNITS):
        lesson_payload = []
        for li, (lesson_slug, name, summary, minutes) in enumerate(lessons):
            row = progress.get(lesson_slug)
            unlocked = lesson_unlocked(ui, li, progress)
            status = row.status if row else ("available" if unlocked else "locked")
            playable = lesson_slug in LESSON_CONTENT
            if next_lesson is None and unlocked and status != "completed" and playable:
                next_lesson = lesson_slug
            lesson_payload.append({"slug":lesson_slug,"title":name,"summary":summary,"minutes":minutes,"status":status,"playable":playable,"bestScore":row.best_score if row else 0})
        complete = sum(1 for item in lesson_payload if item["status"] in ("completed", "mastered"))
        units.append({"slug":slug,"title":title,"description":description,"icon":icon,"number":ui+1,"lessons":lesson_payload,"completed":complete,"total":len(lessons)})
    return {"learner":{"id":person.id,"name":person.display_name,"xp":person.xp,"streak":person.streak,"dailyGoal":person.daily_goal},"units":units,"nextLesson":next_lesson}

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/api/course")
def get_course(learner_id: str, db: Session = Depends(get_db)):
    return course_payload(db, learner_id)

@app.get("/api/dashboard")
def dashboard(learner_id: str, db: Session = Depends(get_db)):
    course = course_payload(db, learner_id)
    progress = progress_map(db, learner_id)
    completed = sum(1 for row in progress.values() if row.status in ("completed", "mastered"))
    attempts = db.scalars(select(ExerciseAttempt).join(LessonSession).where(LessonSession.learner_id == learner_id)).all()
    correct = sum(row.correct for row in attempts)
    accuracy = round(correct / len(attempts) * 100) if attempts else 0
    return {**course, "stats":{"completed":completed,"accuracy":accuracy,"attempts":len(attempts),"review":sum(1 for row in progress.values() if row.best_score < 80)}}

@app.post("/api/lessons/{slug}/sessions")
def start_session(slug: str, body: StartBody, db: Session = Depends(get_db)):
    content = LESSON_CONTENT.get(slug)
    found = find_lesson(slug)
    if not content or not found:
        raise HTTPException(404, "This lesson is not authored yet")
    person = learner(db, body.learner_id)
    if not lesson_unlocked(found[0], found[1], progress_map(db, person.id)):
        raise HTTPException(403, "Complete the previous lesson first")
    active = db.scalar(select(LessonSession).where(LessonSession.learner_id == person.id, LessonSession.lesson_slug == slug, LessonSession.status == "active").order_by(LessonSession.created_at.desc()))
    if not active:
        active = LessonSession(learner_id=person.id, lesson_slug=slug)
        db.add(active)
        db.commit()
        db.refresh(active)
    return session_payload(active, content)

def session_payload(session: LessonSession, content: dict):
    cards = content["cards"]
    return {"id":session.id,"lesson":{"slug":session.lesson_slug,"eyebrow":content["eyebrow"],"title":content["title"],"description":content["description"]},"position":session.position,"total":len(cards),"hearts":session.hearts,"xpEarned":session.xp_earned,"status":session.status,"card":public_card(cards[session.position]) if session.position < len(cards) else None}

def normalize(value):
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(LessonSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session_payload(session, LESSON_CONTENT[session.lesson_slug])

@app.post("/api/sessions/{session_id}/answer")
def answer(session_id: str, body: AnswerBody, db: Session = Depends(get_db)):
    session = db.get(LessonSession, session_id)
    if not session or session.status != "active":
        raise HTTPException(409, "This session is not active")
    content = LESSON_CONTENT[session.lesson_slug]
    card = content["cards"][session.position]
    if card["type"] == "story":
        correct = True
    elif card["type"] == "number":
        try: correct = abs(float(body.answer) - float(card["answer"])) <= card.get("tolerance", 0)
        except (TypeError, ValueError): correct = False
    else:
        correct = normalize(body.answer) == normalize(card["answer"])
    previous_correct = db.scalar(select(ExerciseAttempt).where(ExerciseAttempt.session_id == session.id, ExerciseAttempt.exercise_id == card["id"], ExerciseAttempt.correct == 1))
    if previous_correct:
        return {"correct":True,"explanation":card.get("explanation", ""),"xpAwarded":0,"alreadyAccepted":True}
    xp = 0
    if correct:
        earlier = db.scalar(select(ExerciseAttempt).where(ExerciseAttempt.session_id == session.id, ExerciseAttempt.exercise_id == card["id"]))
        xp = 6 if earlier else (2 if card["type"] == "story" else 10)
        session.correct += 1
        session.xp_earned += xp
    else:
        session.hearts = max(0, session.hearts - 1)
        session.mistakes += 1
    db.add(ExerciseAttempt(session_id=session.id, exercise_id=card["id"], answer={"value":body.answer}, correct=1 if correct else 0))
    db.commit()
    return {"correct":correct,"explanation":card.get("explanation", "Take another look at the mental model and try again."),"xpAwarded":xp,"hearts":session.hearts}

@app.post("/api/sessions/{session_id}/advance")
def advance(session_id: str, db: Session = Depends(get_db)):
    session = db.get(LessonSession, session_id)
    if not session or session.status != "active":
        raise HTTPException(409, "This session is not active")
    content = LESSON_CONTENT[session.lesson_slug]
    card = content["cards"][session.position]
    accepted = card["type"] == "story" or db.scalar(select(ExerciseAttempt).where(ExerciseAttempt.session_id == session.id, ExerciseAttempt.exercise_id == card["id"], ExerciseAttempt.correct == 1))
    if not accepted:
        raise HTTPException(409, "Answer correctly before continuing")
    session.position += 1
    if session.position >= len(content["cards"]):
        session.status = "completed"
        person = db.get(Learner, session.learner_id)
        bonus = 20 if session.mistakes == 0 else 10
        session.xp_earned += bonus
        person.xp += session.xp_earned
        today = date.today()
        if person.last_active_date != today:
            person.streak = person.streak + 1 if person.last_active_date == today - timedelta(days=1) else 1
            person.last_active_date = today
        row = db.scalar(select(LessonProgress).where(LessonProgress.learner_id == person.id, LessonProgress.lesson_slug == session.lesson_slug))
        if not row:
            row = LessonProgress(learner_id=person.id, lesson_slug=session.lesson_slug)
            db.add(row)
        score = round(session.correct / max(1, session.correct + session.mistakes) * 100)
        row.status = "completed"
        row.best_score = max(row.best_score, score)
        row.attempts += 1
        row.completed_at = datetime.now().astimezone()
        db.commit()
        return {"completed":True,"xpEarned":session.xp_earned,"score":score,"perfect":session.mistakes == 0,"streak":person.streak}
    db.commit()
    db.refresh(session)
    return session_payload(session, content)

@app.get("/api/progress")
def get_progress(learner_id: str, db: Session = Depends(get_db)):
    return dashboard(learner_id, db)
