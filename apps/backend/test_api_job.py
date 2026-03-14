import asyncio
import httpx

async def run():
    print("Testing bulk upload via API WITH job_id...")
    async with httpx.AsyncClient(timeout=30) as client:
        # Create a cohort
        resp = await client.post("http://localhost:8000/api/v1/admin/cohorts", json={"name": "Test Cohort"})
        print("Cohort response:", resp.status_code, resp.text)
        if resp.status_code != 200:
            return
        cohort_id = resp.json()["cohort_id"]

        # Create a dummy job
        resp = await client.post("http://localhost:8000/api/v1/jobs/upload", json={
            "job_descriptions": ["Looking for a software engineer with Python experience."],
            "resume_id": None
        })
        print("Job response:", resp.status_code, resp.text)
        if resp.status_code != 200:
            return
        job_id = resp.json()["job_id"][0]
        
        # Upload a resume with the job_id
        with open("test.pdf", "rb") as f:
            files = {"files": ("test.pdf", f, "application/pdf")}
            resp = await client.post(
                f"http://localhost:8000/api/v1/admin/cohorts/{cohort_id}/bulk-upload-resumes?job_id={job_id}",
                files=files
            )
        print("Upload response:", resp.status_code, resp.json())

if __name__ == "__main__":
    asyncio.run(run())
