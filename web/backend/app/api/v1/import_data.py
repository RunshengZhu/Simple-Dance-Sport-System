from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict
import uuid
import csv
import io
from app.core.database import get_db
from app.models.competitor import Competitor
from app.models.event import Event

router = APIRouter()


@router.post("/{competition_id}/import-competitors")
async def import_competitors_csv(
    competition_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="请上传CSV文件")

    content = await file.read()
    decoded_content = content.decode('utf-8')

    try:
        reader = csv.DictReader(io.StringIO(decoded_content))
        imported_count = 0
        skipped_count = 0

        for row in reader:
            number = row.get('背番号', '').strip()
            name = row.get('姓名', '').strip()
            unit = row.get('学校/单位', '').strip()
            groups_str = row.get('参赛组别', '').strip()

            if not number or not name:
                skipped_count += 1
                continue

            name_parts = name.split('、')
            is_couple = len(name_parts) == 2
            partner_number = None
            partner_unit = None

            if is_couple:
                main_name = name_parts[0]
            else:
                main_name = name

            existing = await db.execute(select(Competitor).where(
                Competitor.competition_id == competition_id,
                Competitor.number == number
            ))
            if existing.scalar_one_or_none():
                skipped_count += 1
                continue

            competitor = Competitor(
                id=str(uuid.uuid4()),
                competition_id=competition_id,
                number=number,
                name=main_name,
                unit=unit,
                unit_code=unit[:2] if unit else '',
                group_name=groups_str,
                partner_number=partner_number,
                partner_unit=partner_unit,
                is_couple=is_couple
            )
            db.add(competitor)
            imported_count += 1

        await db.commit()
        return {
            "message": f"导入完成",
            "imported": imported_count,
            "skipped": skipped_count,
            "total": imported_count + skipped_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/{competition_id}/import-schedule")
async def import_schedule_csv(
    competition_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="请上传CSV文件")

    content = await file.read()
    decoded_content = content.decode('utf-8')

    try:
        reader = csv.DictReader(io.StringIO(decoded_content))
        imported_count = 0
        skipped_count = 0

        for row in reader:
            event_number = row.get('场次编号', '').strip()
            event_name = row.get('场次名称', '').strip()
            project_name = row.get('项目名称', '').strip()
            project_id = row.get('项目编号', '').strip()
            round_num = row.get('轮次', '').strip()
            scoring_type = row.get('评分类型', '').strip()
            dances = row.get('舞种', '').strip()
            competitor_numbers_str = row.get('参赛选手', '').strip()
            advancement_count = row.get('晋级人数', '').strip()

            if not event_name:
                skipped_count += 1
                continue

            try:
                advancement_int = int(advancement_count) if advancement_count else 8
            except ValueError:
                advancement_int = 8

            dances_list = []
            if dances:
                dances_list = [d.strip() for d in dances.split(',') if d.strip()]

            competitor_numbers = []
            if competitor_numbers_str:
                for num in competitor_numbers_str.split(','):
                    num = num.strip()
                    if num:
                        competitor_numbers.append(num)

            event = Event(
                id=str(uuid.uuid4()),
                competition_id=competition_id,
                name=event_name,
                project_id=project_id,
                round=int(round_num) if round_num.isdigit() else 1,
                scoring_type=scoring_type if scoring_type in ['mark', 'ranking'] else 'mark',
                dances=dances_list,
                advancement_count=advancement_int,
                competitor_numbers=competitor_numbers,
                status="pending"
            )
            db.add(event)
            imported_count += 1

        await db.commit()
        return {
            "message": f"赛程导入完成",
            "imported": imported_count,
            "skipped": skipped_count,
            "total": imported_count + skipped_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"赛程导入失败: {str(e)}")


@router.post("/{competition_id}/setup-from-test-data")
async def setup_from_test_data(
    competition_id: str,
    db: AsyncSession = Depends(get_db)
):
    competitors_file = "/workspace/src/test_data/test_competitors.csv"
    schedule_file = "/workspace/src/test_data/test_schedule.csv"

    try:
        imported_competitors = 0
        imported_events = 0

        with open(competitors_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                number = row.get('背番号', '').strip()
                name = row.get('姓名', '').strip()
                unit = row.get('学校/单位', '').strip()
                groups_str = row.get('参赛组别', '').strip()

                if not number or not name:
                    continue

                name_parts = name.split('、')
                is_couple = len(name_parts) == 2

                if is_couple:
                    main_name = name_parts[0]
                else:
                    main_name = name

                existing = await db.execute(select(Competitor).where(
                    Competitor.competition_id == competition_id,
                    Competitor.number == number
                ))
                if existing.scalar_one_or_none():
                    continue

                competitor = Competitor(
                    id=str(uuid.uuid4()),
                    competition_id=competition_id,
                    number=number,
                    name=main_name,
                    unit=unit,
                    unit_code=unit[:2] if unit else '',
                    group_name=groups_str,
                    partner_number=None,
                    partner_unit=None,
                    is_couple=is_couple
                )
                db.add(competitor)
                imported_competitors += 1

        with open(schedule_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                event_number = row.get('场次编号', '').strip()
                event_name = row.get('场次名称', '').strip()
                project_name = row.get('项目名称', '').strip()
                project_id = row.get('项目编号', '').strip()
                round_num = row.get('轮次', '').strip()
                scoring_type = row.get('评分类型', '').strip()
                dances = row.get('舞种', '').strip()
                competitor_numbers_str = row.get('参赛选手', '').strip()
                advancement_count = row.get('晋级人数', '').strip()

                if not event_name:
                    continue

                try:
                    advancement_int = int(advancement_count) if advancement_count else 8
                except ValueError:
                    advancement_int = 8

                dances_list = []
                if dances:
                    dances_list = [d.strip() for d in dances.split(',') if d.strip()]

                competitor_numbers = []
                if competitor_numbers_str:
                    for num in competitor_numbers_str.split(','):
                        num = num.strip()
                        if num:
                            competitor_numbers.append(num)

                event = Event(
                    id=str(uuid.uuid4()),
                    competition_id=competition_id,
                    name=event_name,
                    project_id=project_id,
                    round=int(round_num) if round_num.isdigit() else 1,
                    scoring_type=scoring_type if scoring_type in ['mark', 'ranking'] else 'mark',
                    dances=dances_list,
                    advancement_count=advancement_int,
                    competitor_numbers=competitor_numbers,
                    status="pending"
                )
                db.add(event)
                imported_events += 1

        await db.commit()

        return {
            "message": "测试数据导入完成",
            "competitors_imported": imported_competitors,
            "events_imported": imported_events
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"测试数据文件未找到: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
