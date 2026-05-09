from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import io
import csv
from datetime import datetime
from app.core.database import get_db
from app.models.unit_points import UnitPoints, UnitPointRecord
from app.models.event import Event
from app.models.result import Result
from app.models.competitor import Competitor

router = APIRouter()


@router.get("/{competition_id}/export-ranking")
async def export_ranking(competition_id: str, db: AsyncSession = Depends(get_db)):
    unit_points_result = await db.execute(
        select(UnitPoints).where(UnitPoints.competition_id == competition_id)
    )
    unit_points_list = unit_points_result.scalars().all()

    if not unit_points_list:
        raise HTTPException(status_code=404, detail="暂无排名数据，请先计算总分")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['排名', '单位', '总分', '得分项目数'])

    sorted_units = sorted(unit_points_list, key=lambda x: x.total_points, reverse=True)
    for i, up in enumerate(sorted_units):
        writer.writerow([i + 1, up.unit, f"{up.total_points:.1f}", up.record_count])

    output.seek(0)
    content = output.getvalue().encode('utf-8-sig')

    return {
        "download_url": f"data:text/csv;charset=utf-8-sig,{content.decode('latin-1')}",
        "filename": f"单位总分排名_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    }


@router.get("/{competition_id}/export-event-results")
async def export_event_results(competition_id: str, event_id: str, db: AsyncSession = Depends(get_db)):
    results_result = await db.execute(select(Result).where(Result.event_id == event_id))
    results = results_result.scalars().all()

    if not results:
        raise HTTPException(status_code=404, detail="暂无成绩数据")

    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['名次', '番号', '姓名', '单位', '得分'])

    for r in results:
        writer.writerow([r.rank, r.competitor_number, r.competitor_name, r.unit, r.score])

    output.seek(0)
    content = output.getvalue().encode('utf-8-sig')

    event_name = event.name if event else '场次成绩'
    return {
        "download_url": f"data:text/csv;charset=utf-8-sig,{content.decode('latin-1')}",
        "filename": f"{event_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    }


@router.get("/{competition_id}/export-all-results")
async def export_all_results(competition_id: str, db: AsyncSession = Depends(get_db)):
    events_result = await db.execute(
        select(Event).where(Event.competition_id == competition_id, Event.status == 'completed')
    )
    events = events_result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['场次名称', '轮次', '评分类型', '名次', '番号', '姓名', '单位', '得分'])

    for event in events:
        results_result = await db.execute(select(Result).where(Result.event_id == event.id))
        results = results_result.scalars().all()
        for r in results:
            writer.writerow([
                event.name,
                event.round,
                event.scoring_type,
                r.rank,
                r.competitor_number,
                r.competitor_name,
                r.unit,
                r.score
            ])

    output.seek(0)
    content = output.getvalue().encode('utf-8-sig')

    return {
        "download_url": f"data:text/csv;charset=utf-8-sig,{content.decode('latin-1')}",
        "filename": f"所有场次成绩_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    }
