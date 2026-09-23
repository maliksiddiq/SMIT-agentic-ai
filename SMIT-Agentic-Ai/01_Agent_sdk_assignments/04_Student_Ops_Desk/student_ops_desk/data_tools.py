import json
from pathlib import Path
from typing import Any

from .models import StudentProfile


class CourseRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parent.parent / "courses.json"

    def _load(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            courses = payload.get("courses")
            if not isinstance(courses, list):
                return []
            return [course for course in courses if isinstance(course, dict)]
        except (OSError, json.JSONDecodeError):
            return []

    def list_courses(self) -> str:
        courses = self._load()
        if not courses:
            return "No courses are currently available."
        return "\n".join(f"{c.get('id', 'unknown')}: {c.get('title', 'Untitled')}" for c in courses)

    def get_course(self, course_id: str) -> str:
        course = next((c for c in self._load() if c.get("id") == course_id), None)
        if course is None:
            return f"No course with id {course_id} exists."
        return json.dumps({
            "id": course.get("id"),
            "title": course.get("title"),
            "schedule": course.get("schedule"),
            "policies": course.get("policies", {}),
        }, ensure_ascii=False)

    def get_assignment(self, course_id: str, assignment_id: str) -> str:
        course = next((c for c in self._load() if c.get("id") == course_id), None)
        if course is None:
            return f"No course with id {course_id} exists."
        assignment = next(
            (a for a in course.get("assignments", []) if isinstance(a, dict) and a.get("id") == assignment_id),
            None,
        )
        if assignment is None:
            return f"No assignment with id {assignment_id} exists for course {course_id}."
        return json.dumps(assignment, ensure_ascii=False)


def get_scholarship_resources(profile: StudentProfile) -> str:
    if profile.tier != "scholarship":
        return "Scholarship resources are available only to eligible students."
    return f"Scholarship resources for {profile.course_id}: mentor office hours and the course-support grant."


def list_courses(repository: CourseRepository) -> str:
    return repository.list_courses()


def get_course(repository: CourseRepository, course_id: str) -> str:
    return repository.get_course(course_id)


def get_assignment(repository: CourseRepository, course_id: str, assignment_id: str) -> str:
    return repository.get_assignment(course_id, assignment_id)


def close_ticket(ticket: Any) -> Any:
    """Stopping tool: its value is returned immediately as the run result."""
    return ticket
