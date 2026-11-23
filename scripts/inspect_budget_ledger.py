import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.session import async_engine
from app.services.budget_service import BudgetProtectionService
from sqlalchemy import text

async def main():
    async with async_engine.connect() as conn:
        res = await conn.execute(text(
            "SELECT id, billing_period, job_name, status_code, success, returned_count, billable_count, "
            "estimated_cost, actual_cost, remaining_allowance, requests_left, stop_reason, created_at "
            "FROM webz_usage_ledger ORDER BY id ASC"
        ))
        rows = res.fetchall()
        print(f"Total ledger entries: {len(rows)}")
        print("-" * 140)
        total_actual = 0.0
        total_estimated = 0.0
        for r in rows:
            act_str = f"${float(r[8]):.4f}" if r[8] is not None else "None"
            est_val = float(r[7]) if r[7] is not None else 0.0
            act_val = float(r[8]) if r[8] is not None else 0.0
            total_estimated += est_val
            total_actual += act_val
            print(f"ID {r[0]:02d} | Period: {r[1]} | Job: {r[2][:25]:<25} | Status: {str(r[3]):<4} | "
                  f"Success: {str(r[4]):<5} | Ret: {str(r[5]):<2} | Bill: {str(r[6]):<2} | "
                  f"Est: ${est_val:.4f} | Act: {act_str:<7} | Rem: ${float(r[9]):.4f} | "
                  f"ReqsLeft: {str(r[10]):<5} | Stop: {str(r[11])}")
        
        print("-" * 140)
        print(f"Sum of actual costs:    ${total_actual:.4f}")
        print(f"Sum of estimated costs: ${total_estimated:.4f}")

    # Also inspect period summary from BudgetProtectionService
    from app.db.session import async_session_factory
    async with async_session_factory() as db:
        bs = BudgetProtectionService()
        summary = await bs.get_period_summary(db)
        print("\nBudgetProtectionService Period Summary:")
        print(f"  Billing Period:       {summary.billing_period}")
        print(f"  Monthly Credit:       ${summary.monthly_credit:.4f}")
        print(f"  Collection Ceiling:   ${summary.collection_ceiling:.4f}")
        print(f"  Protected Reserve:    ${summary.protected_reserve:.4f}")
        print(f"  Total Spent:          ${summary.total_spent:.4f}")
        print(f"  Remaining Allowance:  ${summary.remaining_allowance:.4f}")
        print(f"  Requests Dispatched:  {summary.requests_dispatched}")
        print(f"  Requests Successful:  {summary.requests_successful}")
        print(f"  Requests Failed:      {summary.requests_failed}")

    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
