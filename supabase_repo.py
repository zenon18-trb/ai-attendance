import os
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY", "")


class SupabaseRepositoryError(RuntimeError):
    pass


def _request(path: str, method: str = "GET", payload: Optional[Any] = None, user_token: Optional[str] = None) -> Any:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise SupabaseRepositoryError("Supabase server credentials are not configured")
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {user_token or SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    body = None if payload is None else __import__("json").dumps(payload).encode()
    request = Request(f"{SUPABASE_URL}/rest/v1/{path}", data=body, headers=headers, method=method)
    request.add_header("Prefer", "return=representation")
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
            return __import__("json").loads(raw) if raw else None
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise SupabaseRepositoryError(f"Supabase request failed ({error.code})") from error


def ensure_organization(user_id: str, organization_name: str = "AI Attendance System") -> str:
    memberships = _request(f"organization_members?user_id=eq.{user_id}&select=organization_id&limit=1")
    if memberships:
        return memberships[0]["organization_id"]
    org = _request("organizations", "POST", {"name": organization_name[:120], "created_by": user_id})[0]
    organization_id = org["id"]
    _request("organization_members", "POST", {"organization_id": organization_id, "user_id": user_id, "role": "owner"})
    return organization_id


def list_people(organization_id: str) -> List[Dict[str, Any]]:
    return _request(f"people?organization_id=eq.{organization_id}&select=*&order=created_at.desc") or []


def list_attendance(organization_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return _request(f"attendance_logs?organization_id=eq.{organization_id}&select=*&order=captured_at.desc&limit={min(limit, 500)}&offset={max(offset, 0)}") or []


def create_person(organization_id: str, person: Dict[str, Any]) -> Dict[str, Any]:
    return _request("people", "POST", {"organization_id": organization_id, **person})[0]


def upload_face_image(organization_id: str, filename: str, image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise SupabaseRepositoryError("Supabase server credentials are not configured")
    safe_name = filename.replace("/", "_").replace("\\", "_")
    path = f"{organization_id}/{safe_name}"
    request = Request(
        f"{SUPABASE_URL}/storage/v1/object/face-images/{path}",
        data=image_bytes,
        headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "Content-Type": content_type, "x-upsert": "true"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20):
            return path
    except HTTPError as error:
        raise SupabaseRepositoryError("Face image upload failed") from error


def create_signed_image_url(path: str, expires_in: int = 3600) -> str:
    if not path or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return ""
    request = Request(
        f"{SUPABASE_URL}/storage/v1/object/sign/face-images/{path}",
        data=__import__("json").dumps({"expiresIn": expires_in}).encode(),
        headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = __import__("json").loads(response.read())
            return f"{SUPABASE_URL}/storage/v1{result.get('signedURL', '')}"
    except HTTPError as error:
        raise SupabaseRepositoryError("Face image URL generation failed") from error


def create_attendance(organization_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
    return _request("attendance_logs", "POST", {"organization_id": organization_id, **record})[0]


def delete_attendance(organization_id: str, record_id: str) -> None:
    _request(f"attendance_logs?id=eq.{record_id}&organization_id=eq.{organization_id}", "DELETE")


def delete_person(organization_id: str, person_id: str) -> None:
    _request(f"people?id=eq.{person_id}&organization_id=eq.{organization_id}", "DELETE")
