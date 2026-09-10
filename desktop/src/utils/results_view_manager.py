#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结果查看工具模块
"""

from typing import Dict, List, Tuple, Optional
import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..models.data_models import ScoreRecord, ScoringType, Competition, Event, Result, EventStatus
from ..utils.logger import get_logger

logger = get_logger()

# 注册中文字体
def register_chinese_fonts():
    """注册中文字体"""
    try:
        # 尝试注册系统中可用的中文字体
        font_paths = [
            # macOS系统字体路径
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Arial Unicode MS.ttf',
            # Linux系统字体路径
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/arphic/uming.ttc',
            # Windows系统字体路径
            'C:/Windows/Fonts/simhei.ttf',
            'C:/Windows/Fonts/simsun.ttc',
        ]
        
        font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # 对于 TTC 字体文件，需要指定字体索引
                    if font_path.endswith('.ttc'):
                        pdfmetrics.registerFont(TTFont('chinese', font_path, subfontIndex=0))
                    else:
                        pdfmetrics.registerFont(TTFont('chinese', font_path))
                    font_registered = True
                    logger.info(f"成功注册中文字体: {font_path}")
                    break
                except Exception as e:
                    logger.warning(f"注册字体失败 {font_path}: {e}")
                    continue
        
        if not font_registered:
            logger.warning("未找到可用的中文字体，使用默认字体")
            return False
        return True
    except Exception as e:
        logger.error(f"注册中文字体失败: {e}")
        return False

# 尝试注册中文字体
chinese_font_available = register_chinese_fonts()


class ResultsViewManager:
    """结果查看管理器类"""
    
    def __init__(self):
        """初始化结果查看管理器"""
        self.logger = logger
    
    def initialize(self):
        """初始化成绩查看管理器"""
        self.logger.info("成绩查看管理器初始化")
        # 这里可以添加初始化逻辑，如加载配置、连接数据库等
        return True
    
    def get_dance_results_from_data(
        self,
        competition: Competition,
        event: Event,
        dance_name: str
    ) -> Tuple[bool, List[Dict], List[str]]:
        """
        从后台数据获取舞种结果
        
        Args:
            competition: 比赛对象
            event: 场次对象
            dance_name: 舞种名称
            
        Returns:
            (是否成功, 结果列表, 错误信息列表)
        """
        self.logger.debug(f"开始获取舞种结果: {competition.name}, {event.name}, {dance_name}")
        
        errors = []
        
        # 验证场次状态
        if event.status != EventStatus.COMPLETED:
            errors.append("场次未完成，无法获取结果")
            return False, [], errors
        
        # 从后台数据获取结果
        try:
            # 检查是否有结果数据
            if not hasattr(competition, 'results') or not competition.results:
                errors.append("没有找到结果数据")
                return False, [], errors
            
            # 获取当前场次的结果
            event_result = competition.results.get(event.id)
            if not event_result:
                errors.append(f"场次 {event.id} 没有结果数据")
                return False, [], errors
            
            # 从CompetitionResult对象获取结果数据
            results_data = event_result.results_data
            if not results_data:
                errors.append("结果数据格式错误")
                return False, [], errors
            
            # 获取舞种结果
            dance_results = results_data.get('dance_results', {})
            if not dance_results:
                errors.append(f"舞种 {dance_name} 没有结果数据")
                return False, [], errors
            
            # 获取评分详情
            score_details = results_data.get('score_details', {})
            
            # 获取选手信息
            players = results_data.get('players', {})
            
            # 转换结果格式
            results = []
            # 检查是否是顺位制的数据结构（直接从dance_results获取）
            if dance_name in dance_results and isinstance(dance_results[dance_name], dict):
                # 这是顺位制的数据结构，直接从dance_results获取
                dance_data = dance_results[dance_name]
                for competitor_number, competitor_data in dance_data.items():
                    # 尝试先使用原始键，再使用字符串键
                    competitor_name = players.get(competitor_number)
                    if competitor_name is None:
                        competitor_name = players.get(str(competitor_number))
                    if competitor_name is None:
                        competitor_name = f"选手{competitor_number}"
                    
                    # 检查competitor_data是否是SkatingScoreDetail对象
                    if hasattr(competitor_data, 'to_dict'):
                        # 如果是SkatingScoreDetail对象，先转换为字典
                        competitor_dict = competitor_data.to_dict()
                    else:
                        # 否则直接使用
                        competitor_dict = competitor_data
                    
                    result = {
                        'rank': competitor_dict.get('final_rank', ''),
                        'competitor_number': competitor_number,
                        'competitor_name': competitor_name,
                        'dance_name': dance_name,
                        'score': competitor_dict.get('sum_placement', 0),
                        'total_score': competitor_dict.get('sum_placement', 0),
                        'cumulative_votes': competitor_dict.get('cumulative_votes', {}),
                        'sum_placement': competitor_dict.get('sum_placement', 0),
                        'final_rank': competitor_dict.get('final_rank', ''),
                        'placement_counts': competitor_dict.get('placement_counts', {}),
                        'judge_placements': competitor_dict.get('judge_placements', {}),
                        'majority_rank': competitor_dict.get('majority_rank', ''),
                        'details': competitor_dict.get('details', {}),
                        'advancement_status': competitor_dict.get('advancement_status', False),
                        'tied_with': competitor_dict.get('tied_with', [])
                    }
                    results.append(result)
            else:
                # 这是列表形式的数据结构（可能是Mark制或其他格式）
                dance_results_list = dance_results.get(dance_name, [])
                for result in dance_results_list:
                    competitor_number = result.get('competitor_number')
                    # 尝试先使用整数键，再使用字符串键
                    competitor_name = players.get(competitor_number)
                    if competitor_name is None:
                        competitor_name = players.get(str(competitor_number), f"选手{competitor_number}")
                    
                    # 尝试从score_details中获取顺位制的详细投票信息
                    score_detail = {}
                    if isinstance(score_details, dict) and dance_name in score_details:
                        score_detail_dict = score_details[dance_name]
                        if isinstance(score_detail_dict, dict):
                            # 尝试使用competitor_number作为键
                            score_detail_data = score_detail_dict.get(str(competitor_number), {})
                            if not score_detail_data:
                                score_detail_data = score_detail_dict.get(competitor_number, {})
                            
                            # 检查是否是SkatingScoreDetail对象
                            if hasattr(score_detail_data, 'to_dict'):
                                # 如果是SkatingScoreDetail对象，先转换为字典
                                score_detail = score_detail_data.to_dict()
                            else:
                                # 否则直接使用
                                score_detail = score_detail_data
                    
                    # 检查是否包含顺位制特有的字段
                    if 'cumulative_votes' in result or 'placement_counts' in result or 'judge_placements' in result or score_detail:
                        # 这是顺位制的数据结构，但以列表形式存储
                        # 优先使用score_detail中的数据，如果没有则使用result中的数据
                        results.append({
                            'rank': score_detail.get('final_rank', result.get('final_rank', result.get('rank', ''))),
                            'competitor_number': competitor_number,
                            'competitor_name': competitor_name,
                            'dance_name': dance_name,
                            'score': score_detail.get('sum_placement', result.get('score', 0)),
                            'total_score': score_detail.get('sum_placement', result.get('total_score', 0)),
                            'cumulative_votes': score_detail.get('cumulative_votes', result.get('cumulative_votes', {})),
                            'sum_placement': score_detail.get('sum_placement', 0),
                            'final_rank': score_detail.get('final_rank', result.get('final_rank', result.get('rank', ''))),
                            'placement_counts': score_detail.get('placement_counts', result.get('placement_counts', {})),
                            'judge_placements': score_detail.get('judge_placements', result.get('judge_placements', {})),
                            'majority_rank': score_detail.get('majority_rank', result.get('majority_rank', '')),
                            'details': score_detail.get('details', {}),
                            'advancement_status': result.get('advancement_status', False),
                            'tied_with': result.get('tied_with', [])
                        })
                    else:
                        # 这是普通Mark制的数据结构
                        results.append({
                            'rank': result.get('rank'),
                            'competitor_number': competitor_number,
                            'competitor_name': competitor_name,
                            'dance_name': dance_name,
                            'score': result.get('score'),
                            'total_score': result.get('total_score'),
                            'cumulative_votes': {},
                            'sum_placement': 0,
                            'final_rank': result.get('rank'),
                            'placement_counts': {},
                            'judge_placements': {},
                            'majority_rank': '',
                            'details': {},
                            'advancement_status': result.get('advancement_status', False),
                            'tied_with': result.get('tied_with', [])
                        })
            
            self.logger.debug(f"舞种结果获取成功: {len(results)}条记录")
            return True, results, errors
            
        except Exception as e:
            self.logger.error(f"获取舞种结果失败: {e}")
            errors.append(f"获取舞种结果失败: {str(e)}")
            return False, [], errors
    
    def get_overall_results_from_data(
        self,
        competition: Competition,
        event: Event
    ) -> Tuple[bool, List[Dict], List[str]]:
        """
        从后台数据获取综合结果
        
        Args:
            competition: 比赛对象
            event: 场次对象
            
        Returns:
            (是否成功, 结果列表, 错误信息列表)
        """
        self.logger.debug(f"开始获取综合结果: {competition.name}, {event.name}")
        
        errors = []
        
        # 验证场次状态
        if event.status != EventStatus.COMPLETED:
            errors.append("场次未完成，无法获取结果")
            return False, [], errors
        
        # 从后台数据获取结果
        try:
            # 检查是否有结果数据
            if not hasattr(competition, 'results') or not competition.results:
                errors.append("没有找到结果数据")
                return False, [], errors
            
            # 获取当前场次的结果
            event_result = competition.results.get(event.id)
            if not event_result:
                errors.append(f"场次 {event.id} 没有结果数据")
                return False, [], errors
            
            # 从CompetitionResult对象获取结果数据
            results_data = event_result.results_data
            if not results_data:
                errors.append("结果数据格式错误")
                return False, [], errors
            
            # 获取综合结果
            overall_results = results_data.get('overall_results', [])
            if not overall_results:
                errors.append("没有综合结果数据")
                return False, [], errors
            
            # 获取选手信息
            players = results_data.get('players', {})
            
            # 转换结果格式
            results = []
            for result in overall_results:
                competitor_number = result.get('competitor_number')
                # 尝试先使用整数键，再使用字符串键
                competitor_name = players.get(competitor_number)
                if competitor_name is None:
                    competitor_name = players.get(str(competitor_number), f"选手{competitor_number}")
                
                results.append({
                    'rank': result.get('rank'),
                    'competitor_number': competitor_number,
                    'competitor_name': competitor_name,
                    'score': result.get('score'),
                    'total_score': result.get('total_score'),
                    'advancement_status': result.get('advancement_status', False),
                    'tied_with': result.get('tied_with', [])
                })
            
            self.logger.debug(f"综合结果获取成功: {len(results)}条记录")
            return True, results, errors
            
        except Exception as e:
            self.logger.error(f"获取综合结果失败: {e}")
            errors.append(f"获取综合结果失败: {str(e)}")
            return False, [], errors
    
    def get_score_details_from_data(
        self,
        competition: Competition,
        event: Event,
        dance_name: Optional[str] = None
    ) -> Tuple[bool, List[Dict], List[str]]:
        """
        从后台数据获取评分详情
        
        Args:
            competition: 比赛对象
            event: 场次对象
            dance_name: 舞种名称，如果为None则获取所有舞种
            
        Returns:
            (是否成功, 评分详情列表, 错误信息列表)
        """
        self.logger.debug(f"开始获取评分详情: {competition.name}, {event.name}, {dance_name}")
        
        errors = []
        score_details = []
        
        # 验证场次状态
        if event.status != EventStatus.COMPLETED:
            errors.append("场次未完成，无法获取评分详情")
            return False, [], errors
        
        # 从后台数据获取评分记录
        try:
            # 检查是否有评分记录
            if not hasattr(competition, 'score_records') or not competition.score_records:
                errors.append("没有找到评分记录")
                return False, [], errors
            
            # 确定要获取的舞种
            if dance_name:
                dances = [dance_name]
            else:
                dances = [dance.name for dance in event.dances]
            
            # 获取选手信息
            players = {}
            if hasattr(competition, 'results') and competition.results:
                event_result = competition.results.get(event.id)
                if event_result:
                    results_data = event_result.results_data
                    if results_data:
                        players = results_data.get('players', {})
            
            # 获取每个舞种的评分详情
            for d_name in dances:
                for competitor_number in event.competitors:
                    competitor = competition.competitors.get(competitor_number)
                    if not competitor:
                        continue
                    
                    competitor_scores = {
                        "competitor_number": competitor_number,
                        "competitor_name": competitor.name,
                        "dance_name": d_name,
                        "scores": {}
                    }
                    
                    # 获取每个裁判的评分
                    for judge_id, judge in competition.judges.items():
                        # 获取评分记录
                        record = competition.get_score_record(event.id, d_name, judge_id, competitor_number)
                        if record:
                            if event.scoring_type == ScoringType.MARK:
                                competitor_scores["scores"][judge_id] = {
                                    "score": record.score,
                                    "mark": record.mark,
                                    "judge_name": judge.name
                                }
                            else:
                                competitor_scores["scores"][judge_id] = {
                                    "placement": record.placement,
                                    "judge_name": judge.name
                                }
                    
                    score_details.append(competitor_scores)
            
            self.logger.debug(f"评分详情获取成功: {len(score_details)}条记录")
            return True, score_details, errors
            
        except Exception as e:
            self.logger.error(f"获取评分详情失败: {e}")
            errors.append(f"获取评分详情失败: {str(e)}")
            return False, [], errors
    
    def export_results_to_json(
        self,
        results: List[Dict],
        file_path: str,
        result_type: str = "results"
    ) -> Tuple[bool, List[str]]:
        """
        导出结果到JSON文件
        
        Args:
            results: 结果列表
            file_path: 文件路径
            result_type: 结果类型(results/score_details)
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出结果到JSON: {file_path}")
        
        errors = []
        
        try:
            # 准备数据
            data = {
                "result_type": result_type,
                "export_time": datetime.now().isoformat(),
                "results": results
            }
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"结果导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出结果失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors
    
    def export_results_to_csv(
        self,
        results: List[Dict],
        file_path: str,
        result_type: str = "results"
    ) -> Tuple[bool, List[str]]:
        """
        导出结果到CSV文件
        
        Args:
            results: 结果列表
            file_path: 文件路径
            result_type: 结果类型(results/score_details)
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出结果到CSV: {file_path}")
        
        errors = []
        
        try:
            import csv
            
            # 打开文件
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 根据结果类型写入不同的表头和数据
                if result_type == "results":
                    # 写入表头
                    writer.writerow(["排名", "选手编号", "选手姓名", "总分", "平均分"])
                    
                    # 写入数据
                    for result in results:
                        writer.writerow([
                            result.get("rank", ""),
                            result.get("competitor_number", ""),
                            result.get("competitor_name", ""),
                            result.get("total_score", ""),
                            result.get("average_score", "")
                        ])
                
                elif result_type == "score_details":
                    # 写入表头
                    writer.writerow(["选手编号", "选手姓名", "舞种", "裁判ID", "裁判姓名", "分数/名次"])
                    
                    # 写入数据
                    for detail in results:
                        competitor_number = detail.get("competitor_number", "")
                        competitor_name = detail.get("competitor_name", "")
                        dance_name = detail.get("dance_name", "")
                        
                        for judge_id, score_info in detail.get("scores", {}).items():
                            judge_name = score_info.get("judge_name", "")
                            
                            if "score" in score_info:
                                score_value = score_info.get("score", "")
                            else:
                                score_value = score_info.get("placement", "")
                            
                            writer.writerow([
                                competitor_number,
                                competitor_name,
                                dance_name,
                                judge_id,
                                judge_name,
                                score_value
                            ])
            
            self.logger.debug(f"结果导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出结果失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors
    
    def generate_results_summary(
        self,
        competition: Competition,
        event: Event
    ) -> Tuple[bool, Dict, List[str]]:
        """
        生成结果摘要
        
        Args:
            competition: 比赛对象
            event: 场次对象
            
        Returns:
            (是否成功, 结果摘要, 错误信息列表)
        """
        self.logger.debug(f"开始生成结果摘要: {competition.name}, {event.name}")
        
        errors = []
        summary = {
            "competition_name": competition.name,
            "event_name": event.name,
            "event_status": event.status,
            "scoring_type": "Mark制" if event.scoring_type == ScoringType.MARK else "顺位法",
            "dances": [dance.name for dance in event.dances],
            "competitors_count": len(event.competitors),
            "judges_count": len(competition.judges),
            "dance_results": {},
            "overall_results": None
        }
        
        # 如果场次已完成，获取已保存的结果
        if event.status == EventStatus.COMPLETED:
            # 从data_manager获取已保存的结果
            try:
                # 获取比赛结果
                competition_result = competition.results.get(event.id)
                if competition_result and competition_result.results_data:
                    results_data = competition_result.results_data
                    
                    # 处理按舞种分组的结果
                    if "dance_results" in results_data:
                        for dance_name, dance_results in results_data["dance_results"].items():
                            summary["dance_results"][dance_name] = dance_results
                    
                    # 处理综合结果
                    if "overall_results" in results_data:
                        summary["overall_results"] = results_data["overall_results"]
                else:
                    # 如果没有保存的结果，则计算结果
                    # 计算每个舞种的结果
                    for dance in event.dances:
                        dance_name = dance.name  # 从Dance对象中获取name属性
                        success, results, dance_errors = self.get_dance_results_from_data(
                            competition,
                            event,
                            dance_name
                        )
                        
                        if success:
                            summary["dance_results"][dance_name] = results
                        else:
                            errors.extend(dance_errors)
                    
                    # 如果有多个舞种，计算综合结果
                    if len(event.dances) > 1:
                        success, overall_results, overall_errors = self.get_overall_results_from_data(
                            competition,
                            event
                        )
                        
                        if success:
                            summary["overall_results"] = overall_results
                        else:
                            errors.extend(overall_errors)
            except Exception as e:
                self.logger.error(f"获取结果摘要失败: {e}")
                errors.append(f"获取结果摘要失败: {str(e)}")
        
        self.logger.debug(f"结果摘要生成成功: {len(summary['dance_results'])}个舞种结果")
        return len(errors) == 0, summary, errors
    
    def export_advancement_list(
        self,
        event_id: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出晋级名单到Excel文件
        
        Args:
            event_id: 场次ID
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出晋级名单: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 获取场次结果
            success, results, result_errors = self.get_dance_results_from_data(
                competition, event, event.dances[0].name if event.dances else ""
            )
            
            if not success:
                errors.extend(result_errors)
                return False, errors
            
            # 获取晋级人数
            advancement_count = event.advancement_count
            if advancement_count <= 0:
                errors.append("场次未设置晋级人数")
                return False, errors
            
            # 按排名排序并获取晋级选手
            results.sort(key=lambda x: x.get("rank", float('inf')))
            advanced_competitors = results[:advancement_count]
            
            # 导出到Excel
            import pandas as pd
            
            # 准备数据
            data = []
            for i, result in enumerate(advanced_competitors, 1):
                competitor_number = result.get("competitor_number", "")
                # 使用背番号+项目编号获取选手信息
                competitor = data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                competitor_name = competitor.name if competitor else f"选手{competitor_number}"
                competitor_unit = competitor.unit if competitor else ""
                
                data.append({
                    "序号": i,
                    "背番号": competitor_number,
                    "选手姓名": competitor_name,
                    "单位": competitor_unit,
                    "排名": result.get("rank", ""),
                    "总分": result.get("total_score", "")
                })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出到Excel
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            self.logger.debug(f"晋级名单导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出晋级名单失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors
    
    def print_results(
        self,
        results: List[Dict],
        result_type: str = "results",
        title: str = "比赛结果"
    ) -> Tuple[bool, List[str]]:
        """
        打印结果
        
        Args:
            results: 结果列表
            result_type: 结果类型(results/score_details)
            title: 打印标题
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始打印结果: {title}")
        
        errors = []
        
        try:
            # 这里可以实现实际的打印功能
            # 目前只是模拟打印
            print(f"===== {title} =====")
            
            if result_type == "results":
                # 打印结果表格
                print(f"{'排名':<5}{'选手编号':<10}{'选手姓名':<15}{'总分':<10}{'平均分':<10}")
                print("-" * 50)
                
                for result in results:
                    print(f"{result.get('rank', ''):<5}{result.get('competitor_number', ''):<10}"
                          f"{result.get('competitor_name', ''):<15}{result.get('total_score', ''):<10}"
                          f"{result.get('average_score', ''):<10}")
            
            elif result_type == "score_details":
                # 按舞种分组打印评分详情
                dance_groups = {}
                for detail in results:
                    dance_name = detail.get("dance_name", "")
                    if dance_name not in dance_groups:
                        dance_groups[dance_name] = []
                    dance_groups[dance_name].append(detail)
                
                for dance_name, details in dance_groups.items():
                    print(f"\n----- {dance_name} -----")
                    print(f"{'选手编号':<10}{'选手姓名':<15}{'裁判':<10}{'分数/名次':<10}")
                    print("-" * 45)
                    
                    for detail in details:
                        competitor_number = detail.get("competitor_number", "")
                        competitor_name = detail.get("competitor_name", "")
                        
                        for judge_id, score_info in detail.get("scores", {}).items():
                            judge_name = score_info.get("judge_name", "")
                            
                            if "score" in score_info:
                                score_value = score_info.get("score", "")
                            else:
                                score_value = score_info.get("placement", "")
                            
                            print(f"{competitor_number:<10}{competitor_name:<15}"
                                  f"{judge_name}({judge_id}): {score_value:<10}")
            
            print("\n===== 打印完成 =====")
            
            self.logger.debug("结果打印成功")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"打印结果失败: {e}")
            errors.append(f"打印失败: {str(e)}")
            return False, errors

    def export_score_details(
        self,
        event_id: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出评分详情到Excel文件
        
        Args:
            event_id: 场次ID
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出评分详情: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 获取评分详情
            success, score_details, detail_errors = self.get_score_details_from_data(
                competition, event
            )
            
            if not success:
                errors.extend(detail_errors)
                return False, errors
            
            # 导出到Excel
            import pandas as pd
            
            # 准备数据
            data = []
            for detail in score_details:
                competitor_number = detail.get("competitor_number", "")
                competitor_name = detail.get("competitor_name", "")
                dance_name = detail.get("dance_name", "")
                
                for judge_id, score_info in detail.get("scores", {}).items():
                    judge_name = score_info.get("judge_name", "")
                    
                    if "score" in score_info:
                        score_value = score_info.get("score", "")
                    else:
                        score_value = score_info.get("placement", "")
                    
                    data.append({
                        "选手编号": competitor_number,
                        "选手姓名": competitor_name,
                        "舞种": dance_name,
                        "裁判ID": judge_id,
                        "裁判姓名": judge_name,
                        "分数/名次": score_value
                    })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出到Excel
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            self.logger.debug(f"评分详情导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出评分详情失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors
    
    def export_dance_results(
        self,
        event_id: str,
        dance_name: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出舞种结果到Excel文件
        
        Args:
            event_id: 场次ID
            dance_name: 舞种名称
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出舞种结果: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 获取舞种结果
            success, results, result_errors = self.get_dance_results_from_data(
                competition, event, dance_name
            )
            
            if not success:
                errors.extend(result_errors)
                return False, errors
            
            # 导出到Excel
            import pandas as pd
            
            # 准备数据
            data = []
            for result in results:
                competitor_number = result.get("competitor_number", "")
                # 使用背番号+项目编号获取选手信息
                competitor = data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                competitor_name = competitor.name if competitor else f"选手{competitor_number}"
                competitor_unit = competitor.unit if competitor else ""
                
                data.append({
                    "排名": result.get("rank", ""),
                    "选手编号": competitor_number,
                    "选手姓名": competitor_name,
                    "单位": competitor_unit,
                    "总分": result.get("total_score", ""),
                    "分数": result.get("score", "")
                })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出到Excel
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            self.logger.debug(f"舞种结果导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出舞种结果失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors
    
    def export_overall_results(
        self,
        event_id: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出综合结果到Excel文件
        
        Args:
            event_id: 场次ID
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出综合结果: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 获取综合结果
            success, results, result_errors = self.get_overall_results_from_data(
                competition, event
            )
            
            if not success:
                errors.extend(result_errors)
                return False, errors
            
            # 导出到Excel
            import pandas as pd
            
            # 准备数据
            data = []
            for result in results:
                competitor_number = result.get("competitor_number", "")
                # 使用背番号+项目编号获取选手信息
                competitor = data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                competitor_name = competitor.name if competitor else f"选手{competitor_number}"
                competitor_unit = competitor.unit if competitor else ""
                
                # 格式化舞种得分
                dance_scores = []
                for dance_name, score in result.get('dance_scores', {}).items():
                    dance_scores.append(f"{dance_name}: {score}")
                dance_scores_str = ", ".join(dance_scores)
                
                data.append({
                    "排名": result.get("rank", ""),
                    "选手编号": competitor_number,
                    "选手姓名": competitor_name,
                    "单位": competitor_unit,
                    "总分": result.get("total_score", ""),
                    "各舞种得分": dance_scores_str
                })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出到Excel
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            self.logger.debug(f"综合结果导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出综合结果失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors


    def export_dance_results_to_pdf(
        self,
        event_id: str,
        dance_name: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出舞种结果到PDF文件
        
        Args:
            event_id: 场次ID
            dance_name: 舞种名称
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出舞种结果到PDF: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 获取舞种结果
            success, results, result_errors = self.get_dance_results_from_data(
                competition, event, dance_name
            )
            
            if not success:
                errors.extend(result_errors)
                return False, errors
            
            # 创建PDF文档，设置边距
            doc = SimpleDocTemplate(
                file_path, 
                pagesize=A4,
                leftMargin=40,
                rightMargin=40,
                topMargin=40,
                bottomMargin=40
            )
            
            # 获取样式
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            normal_style = styles['Normal']
            
            # 如果中文字体可用，创建自定义样式
            if chinese_font_available:
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
                
                # 创建支持中文的标题样式
                chinese_title_style = ParagraphStyle(
                    'ChineseTitle',
                    parent=title_style,
                    fontName='chinese',
                    fontSize=16,
                    alignment=TA_CENTER,
                    spaceAfter=12
                )
                
                # 创建支持中文的普通文本样式
                chinese_normal_style = ParagraphStyle(
                    'ChineseNormal',
                    parent=normal_style,
                    fontName='chinese',
                    fontSize=10,
                    alignment=TA_LEFT,
                    spaceAfter=6
                )
                
                title_style = chinese_title_style
                normal_style = chinese_normal_style
            
            # 构建内容
            story = []
            
            # 判断是否为非决赛的mark制场次
            is_mark_scoring = event.scoring_type == "Mark制"
            # 根据场次名称判断是否为决赛
            is_final = "决赛" in event.name
            
            # 添加标题 - 对于非决赛的mark制场次，只使用项目场次名称作为标题
            if is_mark_scoring and not is_final:
                title = Paragraph(f"{event.name} - {dance_name} 结果", title_style)
            else:
                title = Paragraph(f"{competition.name} - {event.name} - {dance_name} 结果", title_style)
            story.append(title)
            story.append(Spacer(1, 0.2 * inch))
            
            # 准备表格数据 - 对于非决赛的mark制场次，将"晋级/录取"栏改为"晋级"
            if is_mark_scoring and not is_final:
                table_data = [['排名', '背番号', '选手', '单位', '晋级']]
            else:
                table_data = [['排名', '背番号', '选手', '单位', '晋级/录取']]
            
            # 获取晋级人数
            advancement_count = event.advancement_count
            
            for result in results:
                rank = result.get("rank", "")
                competitor_number = result.get("competitor_number", "")
                # 使用背番号+项目编号获取选手信息
                competitor = data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                competitor_name = competitor.name if competitor else f"选手{competitor_number}"
                competitor_unit = competitor.unit if competitor else ""
                
                # 判断是否晋级
                advancement_status = "是" if advancement_count > 0 and rank <= advancement_count else ""
                
                table_data.append([rank, competitor_number, competitor_name, competitor_unit, advancement_status])
            
            # 计算列宽，使表格适应A4页面
            # A4宽度约为595点，减去边距后约为515点
            col_widths = [
                50,   # 排名列
                70,   # 背番号列
                150,  # 选手列
                150,  # 单位列
                95    # 晋级/录取列
            ]
            
            # 创建表格
            table = Table(table_data, colWidths=col_widths)
            
            # 设置表格样式
            table.setStyle(TableStyle([
                # 表头样式
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'chinese' if chinese_font_available else 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                
                # 数据行样式
                ('FONTNAME', (0, 1), (-1, -1), 'chinese' if chinese_font_available else 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                
                # 所有数据行使用白色背景
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
                
                # 边框
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
            ]))
            
            # 添加表格到内容
            story.append(table)
            
            # 添加页脚
            story.append(Spacer(1, 0.3 * inch))
            footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            footer = Paragraph(footer_text, normal_style)
            story.append(footer)
            
            # 生成PDF
            doc.build(story)
            
            self.logger.debug(f"舞种结果PDF导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出舞种结果PDF失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors
    
    def export_overall_results_to_pdf(
        self,
        event_id: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出综合结果到PDF文件
        
        Args:
            event_id: 场次ID
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出综合结果到PDF: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 获取综合结果
            success, results, result_errors = self.get_overall_results_from_data(
                competition, event
            )
            
            if not success:
                errors.extend(result_errors)
                return False, errors
            
            # 创建PDF文档，设置边距
            doc = SimpleDocTemplate(
                file_path, 
                pagesize=A4,
                leftMargin=40,
                rightMargin=40,
                topMargin=40,
                bottomMargin=40
            )
            
            # 获取样式
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            normal_style = styles['Normal']
            
            # 如果中文字体可用，创建自定义样式
            if chinese_font_available:
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
                
                # 创建支持中文的标题样式
                chinese_title_style = ParagraphStyle(
                    'ChineseTitle',
                    parent=title_style,
                    fontName='chinese',
                    fontSize=16,
                    alignment=TA_CENTER,
                    spaceAfter=12
                )
                
                # 创建支持中文的普通文本样式
                chinese_normal_style = ParagraphStyle(
                    'ChineseNormal',
                    parent=normal_style,
                    fontName='chinese',
                    fontSize=10,
                    alignment=TA_LEFT,
                    spaceAfter=6
                )
                
                title_style = chinese_title_style
                normal_style = chinese_normal_style
            
            # 构建内容
            story = []
            
            # 判断是否为非决赛的mark制场次
            is_mark_scoring = event.scoring_type == "Mark制"
            # 根据场次名称判断是否为决赛
            is_final = "决赛" in event.name
            
            # 添加标题 - 对于非决赛的mark制场次，只使用项目场次名称作为标题
            title = Paragraph(f"{event.name}", title_style)
            story.append(title)
            story.append(Spacer(1, 0.2 * inch))
            
            # 准备表格数据 - 对于非决赛的mark制场次，将"晋级/录取"栏改为"晋级"
            if is_mark_scoring and not is_final:
                table_data = [['排名', '背番号', '选手', '单位', '晋级']]
            else:
                table_data = [['排名', '背番号', '选手', '单位', '录取']]
            
            # 获取晋级人数
            advancement_count = event.advancement_count
            
            for result in results:
                rank = result.get("rank", "")
                competitor_number = result.get("competitor_number", "")
                # 使用背番号+项目编号获取选手信息
                competitor = data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                competitor_name = competitor.name if competitor else f"选手{competitor_number}"
                competitor_unit = competitor.unit if competitor else ""
                
                # 判断是否晋级
                advancement_status = result.get("advancement_status", False)
                advancement_text = "是" if advancement_status else ""
                
                table_data.append([rank, competitor_number, competitor_name, competitor_unit, advancement_text])
            
            # 计算列宽，使表格适应A4页面
            # A4宽度约为595点，减去边距后约为515点
            col_widths = [
                50,   # 排名列
                70,   # 背番号列
                150,  # 选手列
                150,  # 单位列
                95    # 晋级/录取列
            ]
            
            # 创建表格
            table = Table(table_data, colWidths=col_widths)
            
            # 设置表格样式
            table.setStyle(TableStyle([
                # 表头样式
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'chinese' if chinese_font_available else 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                
                # 数据行样式
                ('FONTNAME', (0, 1), (-1, -1), 'chinese' if chinese_font_available else 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                
                # 所有数据行使用白色背景
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
                
                # 边框
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
            ]))
            
            # 添加表格到内容
            story.append(table)
            
            # 添加页脚
            story.append(Spacer(1, 0.3 * inch))
            footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            footer = Paragraph(footer_text, normal_style)
            story.append(footer)
            
            # 生成PDF
            doc.build(story)
            
            self.logger.debug(f"综合结果PDF导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出综合结果PDF失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors
    
    def export_detailed_results_to_pdf(
        self,
        event_id: str,
        file_path: str,
        data_manager
    ) -> Tuple[bool, List[str]]:
        """
        导出详细结果到PDF文件，格式类似示例评分.md
        
        Args:
            event_id: 场次ID
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出详细结果到PDF: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 创建PDF文档，设置边距
            doc = SimpleDocTemplate(
                file_path, 
                pagesize=A4,
                leftMargin=40,
                rightMargin=40,
                topMargin=40,
                bottomMargin=40
            )
            
            # 获取样式
            styles = getSampleStyleSheet()
            
            # 创建支持中文的样式
            if chinese_font_available:
                title_style = ParagraphStyle(
                    'ChineseTitle',
                    parent=styles['Heading1'],
                    fontName='chinese',
                    fontSize=16,
                    spaceAfter=12
                )
                heading_style = ParagraphStyle(
                    'ChineseHeading',
                    parent=styles['Heading2'],
                    fontName='chinese',
                    fontSize=14,
                    spaceAfter=10
                )
                normal_style = ParagraphStyle(
                    'ChineseNormal',
                    parent=styles['Normal'],
                    fontName='chinese',
                    fontSize=10
                )
            else:
                title_style = styles['Heading1']
                heading_style = styles['Heading2']
                normal_style = styles['Normal']
            
            # 构建PDF内容
            story = []
            
            # 判断是否为非决赛的mark制场次
            is_mark_scoring = event.scoring_type == "Mark制"
            # 根据场次名称判断是否为决赛
            is_final = "决赛" in event.name
            
            # 添加标题 - 对于非决赛的mark制场次，只使用项目场次名称作为标题
            if is_mark_scoring and not is_final:
                title = f"{event.name} 详细评分表"
            else:
                title = f"{competition.name} - {event.name} 详细评分表"
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 0.2 * inch))
            
            # 获取评分记录数据
            score_records = []
            try:
                # 尝试从数据管理器获取评分记录
                if hasattr(data_manager, 'get_score_records'):
                    score_records = data_manager.get_score_records(event_id)
            except Exception as e:
                self.logger.warning(f"获取评分记录失败: {e}")
            
            if not score_records:
                errors.append("没有找到评分记录数据")
                return False, errors
            
            # 按舞种分组评分记录
            dance_scores = {}
            for record in score_records:
                # 处理ScoreRecord对象
                if hasattr(record, 'dance_name'):
                    dance_name = record.dance_name
                    judge_id = record.judge_id
                    competitor_number = record.competitor_number
                    score = record.score
                    mark = record.mark
                    placement = record.placement
                else:
                    # 处理字典格式的记录
                    dance_name = record.get('dance_name', '')
                    judge_id = record.get('judge_id', '')
                    competitor_number = record.get('competitor_number', 0)
                    score = record.get('score')
                    mark = record.get('mark')
                    placement = record.get('placement')
                
                if dance_name not in dance_scores:
                    dance_scores[dance_name] = []
                
                dance_scores[dance_name].append({
                    'judge_id': judge_id,
                    'competitor_number': competitor_number,
                    'score': score,
                    'mark': mark,
                    'placement': placement
                })
            
            # 为每个舞种创建评分表格
            for dance_name, records in dance_scores.items():
                # 添加舞种标题
                story.append(Paragraph(f"舞种: {dance_name}", heading_style))
                story.append(Spacer(1, 0.1 * inch))
                
                # 准备表格数据
                table_data = []
                
                # 收集所有裁判和选手
                judges = set()
                competitors = set()
                
                for record in records:
                    judges.add(record['judge_id'])
                    competitors.add(record['competitor_number'])
                
                # 排序 - 选手按背号排序，裁判按ID排序
                competitors = sorted(competitors, key=int)  # 确保按数字排序
                judges = sorted(judges, key=lambda x: (x[0] if x else '', int(x[1:]) if len(x) > 1 and x[1:].isdigit() else 0))
                
                # 根据场次的scoring_type判断评分类型
                is_mark_system = event.scoring_type == ScoringType.MARK
                is_placement_system = event.scoring_type == ScoringType.SKATING
                
                # 创建表头
                header = ['排名', '背番号']
                for judge_id in judges:
                    header.append(judge_id)
                
                if is_mark_system:
                    header.append('小计')
                elif is_placement_system:
                    # 顺位制需要添加排名计算列
                    # 检查是否使用了新的滑冰系统算法
                    is_new_skating_system = False
                    try:
                        # 获取舞种结果
                        success, dance_results, _ = self.get_dance_results_from_data(
                            competition, event, dance_name
                        )
                        if success and dance_results:
                            # 检查第一个结果是否包含新滑冰系统算法的标记
                            first_result = dance_results[0] if dance_results else {}
                            is_new_skating_system = first_result.get("is_new_skating_system", False)
                    except Exception as e:
                        self.logger.warning(f"检查滑冰系统算法失败: {e}")
                    
                    if is_new_skating_system:
                        # 新滑冰系统算法：裁判打分 + 平均排名 + 最终排名
                        for judge_id in judges:
                            header.append(f"裁判{judge_id}")
                        header.append("平均排名")
                        header.append("最终排名")
                    else:
                        # 原始算法：根据选手数量动态生成区间列 + 1个排名列
                        num_competitors = len(competitors)
                        range_columns = ['1'] + [f'1-{i}' for i in range(2, num_competitors + 1)]
                        header.extend(range_columns + ['名次'])
                else:
                    header.append('小计')  # 默认情况
                
                table_data.append(header)
                
                # 获取舞种结果，用于排序选手
                try:
                    success, dance_results, _ = self.get_dance_results_from_data(
                        competition, event, dance_name
                    )
                    if not success:
                        dance_results = []
                except Exception as e:
                    self.logger.warning(f"获取舞种结果失败: {e}")
                    dance_results = []
                
                # 按照排名对选手进行排序
                # 首先创建选手排名映射
                competitor_rank_map = {}
                for result in dance_results:
                    competitor_number = result.get("competitor_number")
                    rank = result.get("rank", float('inf'))
                    competitor_rank_map[competitor_number] = rank
                
                # 然后按照排名对选手进行排序
                sorted_competitors = sorted(
                    competitors, 
                    key=lambda c: (competitor_rank_map.get(c, float('inf')), c)  # 按排名排序，排名相同时按背号排序
                )
                
                # 为每个选手创建一行
                for competitor in sorted_competitors:
                    # 获取该选手的排名
                    rank = competitor_rank_map.get(competitor, "")
                    rank = str(rank) if rank != float('inf') else ""
                    
                    row = [rank, str(competitor)]  # 添加排名和背番号
                    total_score = 0
                    mark_count = 0  # 用于统计Mark制的数量
                    
                    # 获取该选手在该舞种的评分
                    for judge_id in judges:
                        # 查找该选手和裁判的评分记录
                        found_record = None
                        for record in records:
                            if record['competitor_number'] == competitor and record['judge_id'] == judge_id:
                                found_record = record
                                break
                        
                        # 设置单元格值
                        if found_record:
                            # 对于不同评分类型，优先处理不同的字段
                            if is_mark_system:
                                # Mark制：优先处理mark字段
                                if 'mark' in found_record:
                                    # 对于Mark制，无论mark值是True还是False，都要显示对勾或空白
                                    # 使用"√"代替"✓"，因为"√"在中文字体中更常用且兼容性更好
                                    cell_value = '√' if found_record['mark'] else ''
                                    if found_record['mark']:
                                        mark_count += 1
                                elif found_record['score'] is not None:
                                    cell_value = str(found_record['score'])
                                    total_score += found_record['score']
                                else:
                                    cell_value = ''
                            elif is_placement_system:
                                # 顺位制：优先处理placement字段
                                if found_record['placement'] is not None:
                                    cell_value = str(found_record['placement'])
                                elif found_record['score'] is not None:
                                    cell_value = str(found_record['score'])
                                    total_score += found_record['score']
                                else:
                                    cell_value = ''
                            else:
                                # 默认情况：按顺序检查所有字段
                                if 'mark' in found_record:
                                    cell_value = '√' if found_record['mark'] else ''
                                    if found_record['mark']:
                                        mark_count += 1
                                elif found_record['score'] is not None:
                                    cell_value = str(found_record['score'])
                                    total_score += found_record['score']
                                elif found_record['placement'] is not None:
                                    cell_value = str(found_record['placement'])
                                else:
                                    cell_value = ''
                        else:
                            cell_value = ''
                        
                        row.append(cell_value)
                    
                    # 添加小计或排名信息
                    if is_mark_system:
                        # Mark制：显示Mark数量
                        row.append(str(mark_count))
                    elif is_placement_system:
                        # 顺位制：从后台获取排名数据，不再进行计算
                        
                        # 尝试从后台数据获取该选手在该舞种的排名信息
                        dance_result = None
                        try:
                            # 获取舞种结果
                            success, dance_results, _ = self.get_dance_results_from_data(
                                competition, event, dance_name
                            )
                            if success:
                                for result in dance_results:
                                    if result.get("competitor_number") == competitor:
                                        dance_result = result
                                        break
                        except Exception as e:
                            self.logger.warning(f"获取舞种结果失败: {e}")
                        
                        if dance_result:
                            if is_new_skating_system:
                                # 新滑冰系统算法：显示裁判打分详情
                                individual_rankings = dance_result.get("individual_rankings", {})
                                final_rank = dance_result.get("final_rank", "")
                                average_ranking = dance_result.get("average_ranking", 0)
                                
                                # 添加每个裁判的打分
                                for judge_id in judges:
                                    judge_rank = individual_rankings.get(judge_id, 0)
                                    row.append(str(judge_rank))
                                
                                # 添加平均排名和最终排名
                                row.append(f"{average_ranking:.2f}")
                                row.append(str(final_rank))
                            else:
                                # 原始算法：使用累计票数
                                # 从后台数据获取排名信息
                                cumulative_votes = dance_result.get("cumulative_votes", {})
                                final_rank = dance_result.get("final_rank", "")
                                sum_placement = dance_result.get("sum_placement", 0)
                                details = dance_result.get("details", {})
                                range_stats = details.get("range_stats", {})
                                
                                # 添加区间统计 - 根据选手数量动态生成
                                num_competitors = len(competitors)
                                range_names = ['1'] + [f'1-{i}' for i in range(2, num_competitors + 1)]
                                for range_name in range_names:
                                    if range_name in range_stats:
                                        # 获取range_stats中的数据
                                        range_data = range_stats[range_name]
                                        if isinstance(range_data, dict):
                                            # 检查count值，如果为0则显示空白
                                            count = range_data.get('count', 0)
                                            if count == 0:
                                                row.append('')
                                            elif 'formatted' in range_data:
                                                row.append(range_data['formatted'])
                                            else:
                                                row.append(str(count))
                                        else:
                                            # 如果不是字典类型，直接转换为字符串
                                            value = str(range_data)
                                            row.append('' if value == '0' else value)
                                    else:
                                        # 如果range_stats中没有该区间数据，则显示空白
                                        row.append('')
                                
                                # 添加最终排名
                                row.append(str(final_rank))
                        else:
                            # 如果无法获取后台数据，则添加空值
                            if is_new_skating_system:
                                # 新滑冰系统算法：每个裁判打分 + 平均排名 + 最终排名
                                for _ in judges:
                                    row.append('')
                                row.append('')
                                row.append('')
                            else:
                                # 原始算法：根据选手数量动态生成区间列 + 1个排名列
                                num_competitors = len(competitors)
                                for _ in range(num_competitors + 1):  # 区间列 + 1个排名列
                                    row.append('')
                    else:
                        # 默认情况：显示数值分数或Mark数量
                        if total_score > 0:
                            row.append(str(total_score))
                        elif mark_count > 0:
                            row.append(str(mark_count))
                        else:
                            row.append('')
                    
                    table_data.append(row)
                
                # 创建表格
                # 计算列宽，使表格适应A4页面
                # A4宽度约为595点，减去边距后约为515点
                # 根据列数动态计算列宽
                num_cols = len(table_data[0]) if table_data else 1
                # 固定前两列（排名和背番号）的宽度
                fixed_cols_width = 50 + 70  # 排名50，背番号70
                # 剩余宽度平均分配给其他列
                remaining_width = 515 - fixed_cols_width
                remaining_cols = num_cols - 2
                col_width = remaining_width / remaining_cols if remaining_cols > 0 else 50
                
                # 构建列宽列表
                col_widths = [50, 70]  # 排名和背番号
                for _ in range(remaining_cols):
                    col_widths.append(col_width)
                
                table = Table(table_data, colWidths=col_widths)
                
                # 设置表格样式
                table.setStyle(TableStyle([
                    # 表头样式
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'chinese' if chinese_font_available else 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # 数据行样式
                    ('FONTNAME', (0, 1), (-1, -1), 'chinese' if chinese_font_available else 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                    ('TOPPADDING', (0, 1), (-1, -1), 8),
                    
                    # 所有数据行使用白色背景
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
                    
                    # 边框
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
                ]))
                
                # 添加表格到内容
                story.append(table)
                story.append(Spacer(1, 0.2 * inch))
            
            # 添加最终晋级名单或综合结果
            # 判断是否为决赛
            is_final = "决赛" in event.name
            
            # 获取综合结果
            success, results, result_errors = self.get_overall_results_from_data(
                competition, event
            )
            
            if success and results:
                # 添加综合结果标题
                if is_mark_system:
                    # Mark制场次无论是否是决赛，都显示"晋级名单"
                    story.append(Paragraph("晋级名单", heading_style))
                elif is_final:
                    story.append(Paragraph("决赛最终排名", heading_style))
                else:
                    story.append(Paragraph("最终晋级名单", heading_style))
                story.append(Spacer(1, 0.1 * inch))
                
                # 根据场次的scoring_type判断评分类型
                is_mark_system = event.scoring_type == ScoringType.MARK
                is_placement_system = event.scoring_type == ScoringType.SKATING
                
                # 准备表格数据
                if is_mark_system:
                    # Mark制场次：输出综合晋级表
                    final_table = [['背号', '综合得分', '名次', '晋级状态', '下一场次']]
                    
                    # 按排名和分数排序
                    results.sort(key=lambda x: (x.get("rank", float('inf')), -x.get("total_score", 0), x.get("competitor_number", 0)))
                    
                    for result in results:
                        rank = result.get("rank", "")
                        competitor_number = result.get("competitor_number", "")
                        total_score = result.get("total_score", "")
                        advancement_status = result.get("advancement_status", False)
                        
                        # 检查是否有同分情况
                        tied_with = result.get("tied_with", [])
                        if tied_with and len(tied_with) > 0:
                            # 如果有同分，在名次后添加同分标记
                            rank_display = f"{rank}T"
                        else:
                            rank_display = str(rank)
                        
                        # 设置晋级状态显示
                        advancement_display = "晋级" if advancement_status else "淘汰"
                        
                        # 下一场次信息（简化处理）
                        next_event = "决赛 9TH 第 8 场 A 区"
                        
                        final_table.append([str(competitor_number), str(total_score), rank_display, advancement_display, next_event])
                else:
                    # 顺位制场次：输出综合排名和冠亚季军
                    final_table = [['背号', '综合得分', '最终名次']]
                    
                    # 顺位制：按序和从小到大排序，序和相同则按背号从小到大排序
                    results.sort(key=lambda x: (x.get("total_score", float('inf')), x.get("competitor_number", 0)))
                    
                    for result in results:
                        rank = result.get("rank", "")
                        competitor_number = result.get("competitor_number", "")
                        total_score = result.get("total_score", "")
                        
                        # 添加名次描述
                        rank_description = str(rank)
                        if rank == 1:
                            rank_description += "（冠军）"
                        elif rank == 2:
                            rank_description += "（亚军）"
                        elif rank == 3:
                            rank_description += "（季军）"
                        
                        final_table.append([str(competitor_number), str(total_score), rank_description])
                
                # 创建表格
                # 计算列宽，使表格适应A4页面
                num_cols = len(final_table[0]) if final_table else 1
                # 固定列宽
                if num_cols == 5:  # Mark制，包含晋级状态
                    col_widths = [70, 100, 50, 80, 200]  # 背号70，综合得分100，名次50，晋级状态80，下一场次200
                elif num_cols == 4:
                    col_widths = [70, 100, 50, 200]  # 背号70，综合得分100，名次50，下一场次200
                else:
                    col_widths = [70, 100, 150]  # 背号70，综合得分100，最终名次150
                
                final_table_obj = Table(final_table, colWidths=col_widths)
                
                # 设置表格样式
                final_table_obj.setStyle(TableStyle([
                    # 表头样式
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'chinese' if chinese_font_available else 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # 数据行样式
                    ('FONTNAME', (0, 1), (-1, -1), 'chinese' if chinese_font_available else 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                    ('TOPPADDING', (0, 1), (-1, -1), 8),
                    
                    # 所有数据行使用白色背景
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
                    
                    # 边框
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
                ]))
                
                # 添加表格到内容
                story.append(final_table_obj)
                story.append(Spacer(1, 0.2 * inch))
            
            # 添加页脚
            story.append(Spacer(1, 0.3 * inch))
            footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            footer = Paragraph(footer_text, normal_style)
            story.append(footer)
            
            # 生成PDF
            doc.build(story)
            
            self.logger.debug(f"详细结果PDF导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出详细结果PDF失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors


    def export_score_details_to_markdown(
        self,
        event_id: str,
        file_path: str,
        data_manager,
        event_type: str = None
    ) -> Tuple[bool, List[str]]:
        """
        导出打分明细到Markdown文件，格式与示例评分.md完全一致
        
        Args:
            event_id: 场次ID
            file_path: 导出文件路径
            data_manager: 数据管理器实例
            event_type: 场次类型（半决赛/决赛），如果不提供则自动判断
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出打分明细到Markdown: {event_id} -> {file_path}")
        
        errors = []
        
        try:
            # 获取比赛和场次信息
            competition = data_manager.get_competition()
            event = competition.get_event(event_id)
            
            if not event:
                errors.append(f"找不到场次: {event_id}")
                return False, errors
            
            # 如果没有提供event_type，则根据场次名称自动判断
            if event_type is None:
                event_name = event.name.lower()
                if "半决赛" in event_name:
                    event_type = "半决赛"
                elif "决赛" in event_name:
                    event_type = "决赛"
                else:
                    # 如果名称中没有明确标识，则默认为半决赛
                    event_type = "半决赛"
                    self.logger.warning(f"场次 {event_id} 的名称 '{event.name}' 中未明确标识轮次，默认为半决赛")
            
            self.logger.info(f"场次 {event_id} 被识别为: {event_type}")
            
            # 获取评分记录数据
            score_records = []
            try:
                # 尝试从数据管理器获取评分记录
                if hasattr(data_manager, 'get_score_records'):
                    score_records = data_manager.get_score_records(event_id)
            except Exception as e:
                self.logger.warning(f"获取评分记录失败: {e}")
            
            if not score_records:
                errors.append("没有找到评分记录数据")
                return False, errors
            
            # 按舞种分组评分记录
            dance_scores = {}
            for record in score_records:
                # 处理ScoreRecord对象
                if hasattr(record, 'dance_name'):
                    dance_name = record.dance_name
                    judge_id = record.judge_id
                    competitor_number = record.competitor_number
                    score = record.score
                    mark = record.mark
                    placement = record.placement
                else:
                    # 处理字典格式的记录
                    dance_name = record.get('dance_name', '')
                    judge_id = record.get('judge_id', '')
                    competitor_number = record.get('competitor_number', 0)
                    score = record.get('score')
                    mark = record.get('mark')
                    placement = record.get('placement')
                
                if dance_name not in dance_scores:
                    dance_scores[dance_name] = []
                
                dance_scores[dance_name].append({
                    'judge_id': judge_id,
                    'competitor_number': competitor_number,
                    'score': score,
                    'mark': mark,
                    'placement': placement
                })
            
            # 获取比赛和场次信息
            competition_name = competition.name
            event_name = event.name
            
            # 获取晋级人数
            advancement_count = event.advancement_count
            
            # 获取舞种名称映射
            dance_name_mapping = {
                'W': '华尔兹',
                'T': '探戈',
                'VW': '维也纳华尔兹',
                'F': '狐步',
                'Q': '快步'
            }
            
            # 创建Markdown内容
            markdown_content = []
            
            # 添加主标题
            markdown_content.append(f"# {competition_name} - {event_name} 打分明细\n")
            
            # 添加各舞曲打分明细标题
            markdown_content.append("## 各舞曲打分明细\n")
            
            # 为每个舞种创建评分表格
            for dance_name, records in dance_scores.items():
                # 获取舞种全名
                full_dance_name = dance_name_mapping.get(dance_name, dance_name)
                
                # 添加舞种标题
                markdown_content.append(f"### 舞曲 {dance_name}（{full_dance_name}）\n")
                
                # 准备表格数据
                table_data = []
                
                # 收集所有裁判和选手
                judges = set()
                competitors = set()
                
                for record in records:
                    judges.add(record['judge_id'])
                    competitors.add(record['competitor_number'])
                
                # 排序
                competitors = sorted(competitors)
                judges = sorted(judges)
                
                # 根据场次的scoring_type判断评分类型，而不是根据记录中的字段
                is_mark_system = event.scoring_type == ScoringType.MARK
                is_placement_system = event.scoring_type == ScoringType.SKATING
                
                # 初始化滑冰系统算法标志
                is_new_skating_system = False
                
                # 如果是顺位制，检查是否使用了新的滑冰系统算法
                if is_placement_system:
                    try:
                        # 获取舞种结果
                        success, dance_results, _ = self.get_dance_results_from_data(
                            competition, event, dance_name
                        )
                        if success and dance_results:
                            # 检查第一个结果是否包含新滑冰系统算法的标记
                            first_result = dance_results[0] if dance_results else {}
                            is_new_skating_system = first_result.get("is_new_skating_system", False)
                    except Exception as e:
                        self.logger.warning(f"检查滑冰系统算法失败: {e}")
                
                # 添加日志确保计分方式和场次类型对应
                self.logger.info(f"场次 {event_id} 的评分类型: {event.scoring_type.value}, "
                                f"判断为: {'Mark制' if is_mark_system else '顺位制' if is_placement_system else '未知'}")
                self.logger.debug(f"是否使用新滑冰系统算法: {is_new_skating_system}")
                
                # 创建表头
                header = ['背号']
                for judge_id in judges:
                    header.append(judge_id)
                
                if is_mark_system:
                    header.append('小计')
                elif is_placement_system:
                    # 顺位制需要添加排名计算列（根据选手数量动态生成）
                    num_competitors = len(competitors)
                    range_columns = ['1'] + [f'1-{i}' for i in range(2, num_competitors + 1)]
                    header.extend(range_columns + ['名次'])
                else:
                    header.append('小计')
                
                table_data.append(header)
                
                # 为每个选手创建一行，并收集分数信息用于排序
                competitor_rows = []
                for competitor in competitors:
                    row = [str(competitor)]
                    total_score = 0
                    mark_count = 0  # 用于统计Mark制的数量
                    
                    # 获取该选手在该舞种的评分
                    for judge_id in judges:
                        # 查找该选手和裁判的评分记录
                        score_value = None
                        for record in records:
                            if record['competitor_number'] == competitor and record['judge_id'] == judge_id:
                                # 根据评分类型获取值
                                if record['score'] is not None:
                                    score_value = record['score']
                                elif record['placement'] is not None:
                                    score_value = record['placement']
                                elif record['mark'] is not None:
                                    score_value = '✓' if record['mark'] else ''
                                    if record['mark']:
                                        mark_count += 1
                                break
                        
                        # 设置单元格值
                        if score_value is None:
                            cell_value = ''
                        elif isinstance(score_value, bool):
                            cell_value = '✓' if score_value else ''
                            if score_value:
                                mark_count += 1
                        else:
                            cell_value = str(score_value)
                        
                        row.append(cell_value)
                        
                        # 累计分数（只对数值类型的分数）
                        if isinstance(score_value, (int, float)):
                            total_score += score_value
                    
                    # 添加小计或排名
                    if is_mark_system:
                        # Mark制显示勾选数量
                        row.append(str(mark_count))
                        # 使用mark_count作为排序依据
                        sort_key = mark_count
                    elif is_placement_system:
                        # 顺位制：从后台获取排名数据，不再进行计算
                        # 检查是否使用了新的滑冰系统算法
                        is_new_skating_system = False
                        try:
                            # 获取舞种结果
                            success, dance_results, _ = self.get_dance_results_from_data(
                                competition, event, dance_name
                            )
                            if success and dance_results:
                                # 检查第一个结果是否包含新滑冰系统算法的标记
                                first_result = dance_results[0] if dance_results else {}
                                is_new_skating_system = first_result.get("is_new_skating_system", False)
                        except Exception as e:
                            self.logger.warning(f"检查滑冰系统算法失败: {e}")
                        
                        # 尝试从后台数据获取该选手在该舞种的排名信息
                        dance_result = None
                        try:
                            # 获取舞种结果
                            success, dance_results, _ = self.get_dance_results_from_data(
                                competition, event, dance_name
                            )
                            if success:
                                # 调试输出
                                self.logger.debug(f"获取到舞种结果数量: {len(dance_results)}")
                                for result in dance_results:
                                    self.logger.debug(f"选手: {result.get('competitor_number')}, final_rank: {result.get('final_rank')}, cumulative_votes: {result.get('cumulative_votes')}")
                                
                                # 查找当前选手的结果
                                for result in dance_results:
                                    if str(result.get("competitor_number")) == str(competitor):
                                        dance_result = result
                                        self.logger.debug(f"找到选手 {competitor} 的结果: {dance_result}")
                                        break
                        except Exception as e:
                            self.logger.warning(f"获取舞种结果失败: {e}")
                        
                        if dance_result:
                            if is_new_skating_system:
                                # 新滑冰系统算法：显示裁判打分详情
                                individual_rankings = dance_result.get("individual_rankings", {})
                                final_rank = dance_result.get("final_rank", "")
                                average_ranking = dance_result.get("average_ranking", 0)
                                
                                # 添加每个裁判的打分
                                for judge_id in judges:
                                    judge_rank = individual_rankings.get(judge_id, 0)
                                    row.append(str(judge_rank))
                                
                                # 添加平均排名和最终排名
                                row.append(f"{average_ranking:.2f}")
                                row.append(str(final_rank))
                                
                                # 使用final_rank作为排序依据
                                try:
                                    sort_key = int(final_rank)
                                except (ValueError, TypeError):
                                    sort_key = float('inf')
                            else:
                                # 原始算法：使用累计票数
                                # 从后台数据获取排名信息
                                cumulative_votes = dance_result.get("cumulative_votes", {})
                                final_rank = dance_result.get("final_rank", "")
                                sum_placement = dance_result.get("sum_placement", 0)
                                details = dance_result.get("details", {})
                                range_stats = details.get("range_stats", {})
                                
                                # 添加区间统计 - 使用details中的range_stats数据（根据选手数量动态生成）
                                num_competitors = len(competitors)
                                range_names = ['1'] + [f'1-{i}' for i in range(2, num_competitors + 1)]
                                for range_name in range_names:
                                    if range_name in range_stats:
                                        # 获取range_stats中的数据
                                        range_data = range_stats[range_name]
                                        if isinstance(range_data, dict):
                                            # 检查count值，如果为0则显示空白
                                            count = range_data.get('count', 0)
                                            if count == 0:
                                                row.append('')
                                            elif 'formatted' in range_data:
                                                row.append(range_data['formatted'])
                                            else:
                                                row.append(str(count))
                                        else:
                                            # 如果不是字典类型，直接转换为字符串
                                            value = str(range_data)
                                            row.append('' if value == '0' else value)
                                    else:
                                        # 如果range_stats中没有该区间数据，则显示空白
                                        row.append('')
                                
                                # 添加最终排名
                                row.append(str(final_rank))
                                # 使用final_rank作为排序依据（final_rank越小越好）
                                # 如果final_rank为空，则使用sum_placement作为备选排序依据
                                if final_rank != "":
                                    try:
                                        sort_key = int(final_rank)
                                    except (ValueError, TypeError):
                                        sort_key = sum_placement if sum_placement > 0 else float('inf')
                                else:
                                    sort_key = sum_placement if sum_placement > 0 else float('inf')
                                
                                # 调试输出
                                self.logger.debug(f"选手 {competitor} 的区间统计: {range_stats}, 最终排名: {final_rank}, 序和: {sum_placement}, 排序依据: {sort_key}")
                        else:
                            # 如果无法获取后台数据，则添加空值
                            self.logger.warning(f"无法获取选手 {competitor} 的舞种结果")
                            if is_new_skating_system:
                                # 新滑冰系统算法：每个裁判打分 + 平均排名 + 最终排名
                                for _ in judges:
                                    row.append('')
                                row.append('')
                                row.append('')
                            else:
                                # 原始算法：根据选手数量动态生成区间列 + 1个排名列
                                num_competitors = len(competitors)
                                for _ in range(num_competitors + 1):  # 区间列 + 排名列
                                    row.append('')
                            sort_key = float('inf')
                    
                    # 将行数据和排序依据保存
                    competitor_rows.append((row, sort_key, competitor))
                
                # 根据排序依据排序（分数从高到低，排名从小到大，背号从小到大）
                if is_mark_system or (not is_placement_system and any(r[1] >= 0 for r in competitor_rows)):
                    # Mark制或分数制：按分数从高到低排序，分数相同则按背号从小到大排序
                    competitor_rows.sort(key=lambda x: (-x[1], x[2]))
                elif is_placement_system:
                    # 顺位制：按final_rank从小到大排序，final_rank相同则按背号从小到大排序
                    competitor_rows.sort(key=lambda x: (x[1], x[2]))
                else:
                    # 其他情况：按背号从小到大排序
                    competitor_rows.sort(key=lambda x: x[2])
                
                # 将排序后的行数据添加到表格
                for row_data, _, _ in competitor_rows:
                    table_data.append(row_data)
                
                # 优化：从最后一列开始向前计算，如果第一个数据区间内仅存在一个值，则该值不应显示
                # 仅对顺位制应用此优化
                if is_placement_system and not is_new_skating_system:
                    self.logger.info(f"应用顺位制优化逻辑，场次 {event_id}，舞种 {dance_name}")
                    
                    # 获取区间列的起始和结束索引
                    num_competitors = len(competitors)
                    range_columns = ['1'] + [f'1-{i}' for i in range(2, num_competitors + 1)]
                    
                    # 找到区间列在表格中的索引范围
                    # 表格结构: [背号, 裁判列..., 区间列..., 名次]
                    # 区间列从裁判列之后开始，到名次列之前结束
                    judge_count = len(judges)
                    range_start_idx = 1 + judge_count  # 跳过背号和裁判列
                    range_end_idx = range_start_idx + len(range_columns)  # 区间列结束位置
                    
                    self.logger.debug(f"区间列: {range_columns}")
                    self.logger.debug(f"区间列索引范围: {range_start_idx} 到 {range_end_idx-1}")
                    
                    # 对每个选手进行优化处理
                    for row_idx, row in enumerate(table_data):
                        if row_idx == 0:  # 跳过表头
                            continue
                            
                        # 从最后一列开始向前查找第一个有数据的区间
                        last_data_col_idx = -1
                        
                        # 遍历所有区间列（从后往前）
                        for i in range(len(range_columns) - 1, -1, -1):
                            col_idx = range_start_idx + i
                            if col_idx < len(row):
                                cell_value = row[col_idx]
                                # 检查单元格是否有有效数据（非空且不是nan）
                                if cell_value and cell_value != "" and cell_value != "nan":
                                    last_data_col_idx = col_idx
                                    break
                        
                        # 如果找到了最后一个有数据的列
                        if last_data_col_idx >= 0:
                            col_name = range_columns[last_data_col_idx - range_start_idx]
                            self.logger.debug(f"选手 {row[0]} 的最后一个有数据的列是 {col_name} (索引 {last_data_col_idx})，值为: {row[last_data_col_idx]}")
                            
                            # 检查该列中所有选手的数据，看是否只有当前选手有数据
                            only_one_value = True
                            for other_row_idx, other_row in enumerate(table_data):
                                if other_row_idx == 0 or other_row_idx == row_idx:  # 跳过表头和当前行
                                    continue
                                if last_data_col_idx < len(other_row):
                                    other_value = other_row[last_data_col_idx]
                                    # 如果其他选手在这一列也有数据，则不是唯一值
                                    if other_value and other_value != "" and other_value != "nan":
                                        only_one_value = False
                                        break
                            
                            # 如果只有当前选手在这一列有数据，则清空该值
                            if only_one_value:
                                self.logger.info(f"清空选手 {row[0]} 在列 {col_name} 的值，因为只有该选手有数据")
                                table_data[row_idx][last_data_col_idx] = ""
                            else:
                                self.logger.debug(f"选手 {row[0]} 在列 {col_name} 的值保留，因为还有其他选手有数据")
                        else:
                            self.logger.debug(f"选手 {row[0]} 没有找到有数据的区间列")
                else:
                    self.logger.info(f"跳过顺位制优化逻辑，is_placement_system={is_placement_system}, is_new_skating_system={is_new_skating_system}")
                
                # 将表格数据转换为Markdown格式
                markdown_table = self._convert_to_markdown_table(table_data)
                markdown_content.append(markdown_table)
                markdown_content.append("")  # 空行分隔
            
            # 如果是半决赛，添加晋级名单
            if event_type == "半决赛":
                markdown_content.append("### 半决赛晋级名单\n")
                
                # 获取半决赛结果
                success, results, result_errors = self.get_overall_results_from_data(
                    competition, event
                )
                
                if success and results:
                    # 根据场次的scoring_type判断评分类型
                    is_mark_system = event.scoring_type == ScoringType.MARK
                    is_placement_system = event.scoring_type == ScoringType.SKATING
                    
                    # 添加日志确保计分方式和场次类型对应
                    self.logger.info(f"半决赛 {event_id} 的评分类型: {event.scoring_type.value}, "
                                    f"判断为: {'Mark制' if is_mark_system else '顺位制' if is_placement_system else '未知'}")
                    
                    # 准备晋级名单表格数据
                    if is_mark_system:
                        # Mark制场次：输出综合晋级表，只包含晋级选手
                        advancement_table = [['背号', '合计得分', '名次', '下一场次']]
                        
                        # 按排名和分数排序
                        results.sort(key=lambda x: (x.get("rank", float('inf')), -x.get("total_score", 0), x.get("competitor_number", 0)))
                        
                        # 获取晋级选手 - 需要正确处理同分情况
                        advanced_competitors = []
                        if advancement_count > 0:
                            if len(results) >= advancement_count:
                                advancement_score = results[advancement_count-1].get("total_score", 0)
                                # 获取所有分数大于等于晋级分数的选手
                                advanced_competitors = [r for r in results if r.get("total_score", 0) >= advancement_score]
                            else:
                                advanced_competitors = results
                        else:
                            advanced_competitors = results
                        
                        for result in advanced_competitors:
                            rank = result.get("rank", "")
                            competitor_number = result.get("competitor_number", "")
                            total_score = result.get("total_score", "")
                            
                            # 检查是否有同分情况
                            tied_with = result.get("tied_with", [])
                            if tied_with and len(tied_with) > 0:
                                # 如果有同分，在名次后添加同分标记
                                rank_display = f"{rank}T"  # 使用T表示同分，更简洁
                            else:
                                rank_display = str(rank)
                            
                            # 下一场次信息（这里简化处理）
                            next_event = f"决赛 9TH 第 8 场 A 区"
                            
                            advancement_table.append([str(competitor_number), str(total_score), rank_display, next_event])
                    else:
                        # 顺位制场次：输出综合排名和冠亚季军
                        advancement_table = [['背号', '综合得分', '最终名次']]
                        
                        # 顺位制：按序和从小到大排序，序和相同则按背号从小到大排序
                        results.sort(key=lambda x: (x.get("total_score", float('inf')), x.get("competitor_number", 0)))
                        
                        for result in results:
                            rank = result.get("rank", "")
                            competitor_number = result.get("competitor_number", "")
                            total_score = result.get("total_score", "")
                            
                            # 添加名次描述
                            rank_description = str(rank)
                            if rank == 1:
                                rank_description += "（冠军）"
                            elif rank == 2:
                                rank_description += "（亚军）"
                            elif rank == 3:
                                rank_description += "（季军）"
                            
                            advancement_table.append([str(competitor_number), str(total_score), rank_description])
                    
                    # 将表格数据转换为Markdown格式
                    markdown_table = self._convert_to_markdown_table(advancement_table)
                    markdown_content.append(markdown_table)
            
            # 如果是决赛，添加最终排名
            elif event_type == "决赛":
                markdown_content.append("### 决赛最终排名\n")
                
                # 获取决赛结果
                success, results, result_errors = self.get_overall_results_from_data(
                    competition, event
                )
                
                if success and results:
                    # 根据场次的scoring_type判断评分类型
                    is_mark_system = event.scoring_type == ScoringType.MARK
                    is_placement_system = event.scoring_type == ScoringType.SKATING
                    
                    # 添加日志确保计分方式和场次类型对应
                    self.logger.info(f"决赛 {event_id} 的评分类型: {event.scoring_type.value}, "
                                    f"判断为: {'Mark制' if is_mark_system else '顺位制' if is_placement_system else '未知'}")
                    
                    # 根据评分类型排序
                    if is_placement_system:
                        # 顺位制：按序和从小到大排序，序和相同则按背号从小到大排序
                        results.sort(key=lambda x: (x.get("total_score", float('inf')), x.get("competitor_number", 0)))
                    else:
                        # Mark制或其他评分制：按排名排序
                        results.sort(key=lambda x: x.get("rank", float('inf')))
                    
                    # 准备最终排名表格数据
                    if is_mark_system:
                        # Mark制场次：输出综合晋级表，只包含晋级选手
                        final_ranking_table = [['背号', '综合得分', '最终名次']]
                        
                        # 按排名和分数排序
                        results.sort(key=lambda x: (x.get("rank", float('inf')), -x.get("total_score", 0), x.get("competitor_number", 0)))
                        
                        for result in results:
                            rank = result.get("rank", "")
                            competitor_number = result.get("competitor_number", "")
                            total_score = result.get("total_score", "")
                            
                            # 检查是否有同分情况
                            tied_with = result.get("tied_with", [])
                            if tied_with and len(tied_with) > 0:
                                # 如果有同分，在名次后添加同分标记
                                rank_display = f"{rank}T"  # 使用T表示同分，更简洁
                            else:
                                rank_display = str(rank)
                            
                            final_ranking_table.append([str(competitor_number), str(total_score), rank_display])
                    else:
                        # 顺位制场次：输出综合排名和冠亚季军
                        final_ranking_table = [['背号', '综合得分', '最终名次']]
                        
                        # 顺位制：按序和从小到大排序，序和相同则按背号从小到大排序
                        results.sort(key=lambda x: (x.get("total_score", float('inf')), x.get("competitor_number", 0)))
                        
                        for result in results:
                            rank = result.get("rank", "")
                            competitor_number = result.get("competitor_number", "")
                            total_score = result.get("total_score", "")
                            
                            # 添加名次描述
                            rank_description = str(rank)
                            if rank == 1:
                                rank_description += "（冠军）"
                            elif rank == 2:
                                rank_description += "（亚军）"
                            elif rank == 3:
                                rank_description += "（季军）"
                            
                            final_ranking_table.append([str(competitor_number), str(total_score), rank_description])
                    
                    # 将表格数据转换为Markdown格式
                    markdown_table = self._convert_to_markdown_table(final_ranking_table)
                    markdown_content.append(markdown_table)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(markdown_content))
            
            self.logger.debug(f"打分明细Markdown导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出打分明细Markdown失败: {e}")
            errors.append(f"导出失败: {str(e)}")
            return False, errors
    
    def _convert_to_markdown_table(self, table_data: List[List[str]]) -> str:
        """
        将表格数据转换为Markdown格式
        
        Args:
            table_data: 表格数据，第一行为表头
            
        Returns:
            Markdown格式的表格字符串
        """
        if not table_data:
            return ""
        
        # 计算每列的最大宽度
        col_widths = [0] * len(table_data[0])
        for row in table_data:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # 构建Markdown表格
        markdown_rows = []
        
        # 添加表头
        header_cells = []
        for i, cell in enumerate(table_data[0]):
            header_cells.append(str(cell).ljust(col_widths[i]))
        markdown_rows.append("| " + " | ".join(header_cells) + " |")
        
        # 添加分隔线
        separator_cells = []
        for width in col_widths:
            separator_cells.append("-" * width)
        markdown_rows.append("| " + " | ".join(separator_cells) + " |")
        
        # 添加数据行
        for row in table_data[1:]:
            data_cells = []
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    data_cells.append(str(cell).ljust(col_widths[i]))
            markdown_rows.append("| " + " | ".join(data_cells) + " |")
        
        return "\n".join(markdown_rows)


# 创建全局结果查看管理器实例
results_view_manager = ResultsViewManager()