from fastapi import APIRouter

router = APIRouter(tags= ["Health"], 
                   prefix="/health")

@router.get("/")
def  health () -> dict:
    return {"status" : "ok"}