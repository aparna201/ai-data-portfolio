"""Who is calling. A real deployment gets this from the hospital's single sign-on; here, a token table."""
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    user_id: str
    role: str            # doctor | nurse | lab_tech | front_desk | housekeeping | patient
    ward: str | None = None
    patient_id: int | None = None   # only for role "patient"


TOKENS = {
    "tok-rao": User("d_rao", "doctor"), "tok-iyer": User("d_iyer", "doctor"), "tok-khan": User("d_khan", "doctor"),
    "tok-nurse-a": User("n_asha", "nurse", ward="A"), "tok-nurse-b": User("n_bela", "nurse", ward="B"),
    "tok-lab": User("lab_1", "lab_tech"), "tok-desk": User("fd_1", "front_desk"),
    "tok-clean": User("hk_1", "housekeeping"),
    "tok-pat1": User("p_1", "patient", patient_id=1), "tok-pat2": User("p_2", "patient", patient_id=2),
}
