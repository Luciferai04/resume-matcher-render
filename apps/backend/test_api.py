import asyncio
import httpx

async def run():
    print("Testing bulk upload via API...")
    async with httpx.AsyncClient() as client:
        # Create a cohort first
        resp = await client.post("http://localhost:8000/api/v1/admin/cohorts", json={"name": "Test Cohort"})
        print("Cohort response:", resp.status_code, resp.text)
        if resp.status_code != 200:
            return
        cohort_id = resp.json()["cohort_id"]
        
        # Upload a resume
        with open("test.pdf", "rb") as f:
            files = {"files": ("test.pdf", f, "application/pdf")}
            resp = await client.post(
                f"http://localhost:8000/api/v1/admin/cohorts/{cohort_id}/bulk-upload-resumes",
                files=files
            )
        print("Upload response:", resp.status_code, resp.json())

if __name__ == "__main__":
    asyncio.run(run())
