"""
CLI interface for the personal assistant system
"""

import os
import re
import sys
import cmd
import time
import logging
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.integration.enhanced_assistant import EnhancedPersonalAssistant

logger = logging.getLogger(__name__)

#交互式循环是从 class InteractiveShell(cmd.Cmd): 开始的。具体来说，交互式循环的核心逻辑是由 cmd.Cmd 类提供的，
# 而 InteractiveShell 继承自 cmd.Cmd，并通过重写和扩展其方法来实现自定义的交互式命令行界面。
class InteractiveShell(cmd.Cmd):#类定义：InteractiveShell 继承自 cmd.Cmd，用于实现交互式命令行界面。
    """
    Interactive shell for the personal assistant system
    """

    intro = """
======================================================================
  ENHANCED PERSONAL ASSISTANT SYSTEM WITH RLHF AND DPO
======================================================================

Type 'help' to see the list of commands, 'exit' to quit
"""
    prompt = "\nYou: "

    def __init__(self, assistant: EnhancedPersonalAssistant, model_name: Optional[str] = None):
        """
        Initialize Interactive Shell

        Args:
            assistant: EnhancedPersonalAssistant object
            model_name: Default model (optional)
        """
        super().__init__()
        self.assistant = assistant
        self.model_name = model_name
        self.conversation_id = None
        self.user_info = None
        self.system_prompt = None
        self.last_query = None


        # Update status display
        self._update_status_display()

        logger.info("Initialized Interactive Shell")

    def _update_status_display(self) -> None:#更新并显示当前系统的状态。
        """Update status display"""
        optimization = "ON" if self.assistant.optimization_enabled else "OFF"
        feedback = "ON" if self.assistant.feedback_collection_enabled else "OFF"
        auto_model = "ON" if self.assistant.auto_select_model else "OFF"
        group_discussion = "ON" if self.assistant.use_group_discussion else "OFF"

        status_info = f"Optimization: {optimization} | Feedback Collection: {feedback} | Auto Model Selection: {auto_model} | Group Discussion: {group_discussion}"

        if self.model_name:
            status_info += f" | Model: {self.model_name}"

        self.status = status_info#根据 self.assistant 的状态（如优化、反馈收集等），生成状态信息并存储在 self.status 中。

    def preloop(self) -> None:#在进入命令行循环之前执行一些初始化操作。
        """Setup before entering the main loop"""
        # Initialize a new conversation
        self.conversation_id = f"conv_{int(time.time())}"#初始化一个新的会话 ID（self.conversation_id）。

    def default2(self, line: str,target_nutrients,yes_number0):#处理用户输入的非命令内容（即普通查询）。You: >? Can you introduce South Korea后调用
        """
        Handle input that does not match any command

        Args:
            line: Input line

        Returns:
            False to continue the loop
        """
        #如果用户输入的不是命令（如 help、exit 等），则调用 self._process_query() 处理查询。
        if line.strip():#line 'Can you introduce Nezha 2'
            rate,response_recipe=self.process_query(line.strip(),target_nutrients,yes_number0)

        return rate,response_recipe

    def default(self, line: str) -> bool:#处理用户输入的非命令内容（即普通查询）。You: >? Can you introduce South Korea后调用
        """
        Handle input that does not match any command

        Args:
            line: Input line

        Returns:
            False to continue the loop
        """
        #如果用户输入的不是命令（如 help、exit 等），则调用 self._process_query() 处理查询。
        if line.strip():#line 'Can you introduce Nezha 2'
            self._process_query(line.strip())
        return False

    def emptyline(self) -> bool:#处理用户输入的空行。
        """
        Handle when the user enters an empty line

        Returns:
            False to continue the loop
        """
        return False

    def load_nutrition_data(self,file_path):
        df = pd.read_excel(file_path)
        df.columns = df.columns.str.strip()  # 去除列名中的空格
        df['食物名称'] = df['食物名称'].str.strip()  # 去除索引中的空格
        # df.set_index('食物名称', inplace=True)
        return df

    def readIngredient(self,choices):
        ingredients = []
        df = pd.read_excel(r'C:\code\zjcode\deepseekrecipe\file\19_nutritional_data.xlsx')  # All ingredients
        df.columns = df.columns.str.strip()  # 去除列名中的空格
        df['食物名称'] = df['食物名称'].str.strip()  # 去除索引中的空格
        column_names = df.columns.tolist()  # Get column names

        for index, row in df.iterrows():  # Iterate over rows
            row_dict = {col: row[col] for col in column_names}  # Create dictionary
            ingredients.append(row_dict)

        food_names = [item['食物名称'] for item in ingredients]  # Extract food names
        matched = []
        for target_string in choices:
            best_match_name, best_index = self.find_best_cosine_match(target_string, food_names)  # Find best match
            matched.append(ingredients[best_index])  # Add matched item dictionary
            #print(f"对于 '{target_string}', 最佳匹配是: {best_match_name}")

        return matched

    # Calculate total nutrient content
    def calculate_nutrients(self,ingredients, nutrition_df):
        nutrition_df.set_index('食物名称', inplace=True)
        matched_ingredients = self.readIngredient([name for name, weight in ingredients])

        nutrient_sums = np.zeros(len(nutrition_df.columns) - 1)  # Adjust according to actual columns
        new_recipe=""
        for matched, (name, weight) in zip(matched_ingredients, ingredients):
            new_ingredient = matched['食物名称']+": "+str(weight)+"克"
            new_recipe=new_recipe + "," + new_ingredient
            new_recipe = new_recipe.lstrip(',')

            if matched['食物名称'].strip() in nutrition_df.index:
                #print(matched['食物名称'].strip())
                nutrient_values = nutrition_df.loc[matched['食物名称'].strip()].values[1:].astype(float)  # Adjust slice to match columns
                nutrient_sums += nutrient_values * (weight / 100)  # Assume nutrient content per 100g

            else:
                print(f"Warning: '{matched['食物名称'].strip()}' not found in nutrition data.")
        return nutrient_sums,matched_ingredients,new_recipe

    # Check suitability
    def check_suitability(self,nutrient_sums, target_nutrients):  # ,recipe,matched_ing):
        # print(nutrient_sums)
        # print(target_nutrients)
        suitability = True
        truenum = 0
        falsenum = 0
        yes = ''
        no = ''
        for i, (key, value) in enumerate(target_nutrients.items()):
            if isinstance(value, float):  # 没有最大摄入量的营养素怎么考虑？
                tolerance = 0.1 * value
                # # 下限和上限
                lower_bound = value - tolerance
                upper_bound = value + tolerance
                if lower_bound <= nutrient_sums[i] <= upper_bound:
                    # suitability = True

                    s1 = f"{key}: {nutrient_sums[i]}符合,"
                    # print(s1)
                    yes = yes + s1
                else:
                    # suitability = False

                    s2 = f"{key}: {nutrient_sums[i]}不合适,"
                    # print(s2)
                    no = no + s2
                # suitability = True

            elif isinstance(value, tuple):
                if value[0] <= nutrient_sums[i] <= value[1]:
                    # suitability=True
                    s3 = f"{key}: {nutrient_sums[i]} within {value},"
                    # print(s3)
                    yes = yes + s3
                else:
                    # suitability=False
                    s4 = f"{key}: {nutrient_sums[i]} not {value},"
                    # print(s4)
                    no = no + s4
            # if suitability == False:#有一个营养素不符合要求break
            #     break
        # 以下是如果truenum>falsenum，suitability = True
        #     if suitability==True:
        #         truenum=truenum+1
        #     else:
        #         falsenum=falsenum+1
        # print(truenum)
        # print(falsenum)
        #
        # if truenum>falsenum:
        #     suitability = True
        # else:
        #     suitability = False
        yes = yes.rstrip(',')
        no = no.rstrip(',')
        return suitability, yes, no

    # Remove brackets and punctuation
    def remove_brackets(self,text):
        text = re.sub(r"（.*?）|\{.*?\}|\[.*?\]|【.*?】", '', text)
        text = re.sub(r"[,;:'\"。，、；：‘’“”]", '', text)
        return text.strip()

    # Find the best cosine similarity match
    def find_best_cosine_match(self,input_str, str_list):
        if "牛肉酱" in input_str:
            max_index = 2175
        elif "宽粉" in input_str:
            max_index = 738
        elif "鸡油" == input_str:
            max_index = 1010
        elif "青虾" in input_str:
            max_index = 2087
        elif "小米辣" in input_str:
            max_index = 1276
        elif "小米椒" in input_str:
            max_index = 1276
        elif "桃米炒蛋" in input_str:
            max_index = 1548
        elif "豉油" in input_str:
            max_index = 294
        elif "鸡胗" in input_str:
            max_index = 1885
        elif "红椒" in input_str:
            max_index = 1275
        elif "麻油" in input_str:
            max_index = 1034
        elif "黑芝麻" in input_str:
            max_index = 1712
        elif "芝麻" in input_str:
            max_index = 1711
        elif "鸽蛋" in input_str:
            max_index = 1997
        elif "果子狸" in input_str:
            max_index = 1721
        elif "糖色" in input_str:
            max_index = 975
        elif "白酒" in input_str:
            max_index = 940
        elif "油皮" in input_str:
            max_index = 982
        elif "卤汁" in input_str:
            max_index = 1753
        elif "天麻" in input_str:
            max_index = 325
        elif "鸡蛋清" in input_str:
            max_index = 1980
        elif "蛋清" in input_str:
            max_index = 1980
        elif "鸡蓉鲍" in input_str:
            max_index = 2106
        elif "泡椒" in input_str:
            max_index = 317
        elif "襄荷" in input_str:
            max_index = 683
        elif "青蒿" in input_str:
            max_index = 414
        elif "肥膘肉" in input_str:
            max_index = 1716
        elif "白矾" in input_str:
            max_index = 974
        elif "生粉" in input_str:
            max_index = 2105
        elif "青笋" in input_str:
            max_index = 439
        elif "肥肉" in input_str:
            max_index = 1716
        elif "食用油" in input_str:
            max_index = 1022
        elif "植物油" in input_str:
            max_index = 1022
        elif "菜油" in input_str:
            max_index = 1016
        elif "咸菜" in input_str:
            max_index = 26
        elif "小菜" in input_str:
            max_index = 26
        elif "低粉" in input_str:
            max_index = 596
        elif "低筋" in input_str:
            max_index = 596
        elif "中筋" in input_str:
            max_index = 1250
        elif "中粉" in input_str:
            max_index = 1250
        elif "高粉" in input_str:
            max_index = 599
        elif "高筋" in input_str:
            max_index = 599
        elif "面粉" in input_str:
            max_index = 1250
        elif "包菜" in input_str:
            max_index = 258
        elif "花肉" in input_str:
            max_index = 1722
        elif "牛奶" in input_str:
            max_index = 2172
        elif "牛大骨" in input_str:
            max_index = 2189
        elif "牛排骨" in input_str:
            max_index = 2189
        elif "牛肋排" in input_str:
            max_index = 1795
        elif "牛小骨" in input_str:
            max_index = 2189
        elif "牛仔骨" in input_str:
            max_index = 2189
        elif "糖糊" in input_str:
            max_index = 2190
        elif "核桃" in input_str:
            max_index = 1669
        elif "蛋液" in input_str:
            max_index = 1976
        elif "奶粉" in input_str:
            max_index = 1941
        elif "黑糖" in input_str:
            max_index = 975
        elif input_str == '糖':
            max_index = 973
        elif input_str == '糖粉':
            max_index = 973
        elif input_str == '花生米':
            max_index = 1699
        elif input_str == '瓜子':
            max_index = 1702
        elif "面包粉" in input_str:
            max_index = 643
        elif "酥粒" in input_str:
            max_index = 991
        elif "粘米" in input_str:
            max_index = 1572
        elif "椰" in input_str:
            max_index = 1647
        elif "马蹄粉" in input_str:
            max_index = 1407
        elif "姜末" in input_str:
            max_index = 1419
        elif "夹心肉" in input_str:
            max_index = 1722
        elif "心肉" in input_str:
            max_index = 1724
        elif "彩椒粉" in input_str:
            max_index = 1131
        elif "彩椒" in input_str:
            max_index = 318
        elif "牛里脊" in input_str:
            max_index = 1798
        elif "青椒" in input_str:
            max_index = 316
        elif "黑椒" in input_str:
            max_index = 18
        elif "腌翅料" in input_str:
            max_index = 1132
        elif "腌料" in input_str:
            max_index = 2192
        elif "红葱" in input_str:
            max_index = 1318
        elif "乳清" in input_str:
            max_index = 1934
        elif "竹炭粉" in input_str:
            max_index = 643
        elif "面条" in input_str:
            max_index = 804
        elif "肉末" in input_str:
            max_index = 1715
        elif "肉糜" in input_str:
            max_index = 1715
        elif "鲜肉" in input_str:
            max_index = 1715
        elif "肉沫" in input_str:
            max_index = 1715
        elif "肉丝" in input_str:
            max_index = 1715
        elif "黄辣丁" in input_str:
            max_index = 2004
        elif "黄骨鱼" in input_str:
            max_index = 2004
        elif "桂鱼" in input_str:
            max_index = 2031
        elif "香叶" in input_str:
            max_index = 1427
        elif "盐" in input_str:
            max_index = 1136
        elif "杭椒" in input_str:
            max_index = 1277
        elif "洛神花" in input_str:
            max_index = 879
        elif "黄芪" in input_str:
            max_index = 324
        elif "黄瓜" in input_str:
            max_index = 334
        elif "老干妈" in input_str:
            max_index = 319
        elif "雪碧" in input_str:
            max_index = 856
        elif "葱末" in input_str:
            max_index = 1316
        elif "葱花" in input_str:
            max_index = 1316
        elif "葱丝" in input_str:
            max_index = 1316
        elif "葱白" in input_str:
            max_index = 1316
        elif "青葱" in input_str:
            max_index = 1316
        elif "牛油果" in input_str:
            max_index = 1536
        elif "猪拱嘴" in input_str:
            max_index = 1734
        elif "芝士" in input_str:
            max_index = 1953
        elif "吐司" in input_str:
            max_index = 283
        elif "抹酱" in input_str:
            max_index = 218
        elif "柱候酱" in input_str:
            max_index = 1057
        elif "照烧酱" in input_str:
            max_index = 1057
        elif "吉利丁" in input_str:
            max_index = 1483
        elif input_str == "蛋黄":
            max_index = 1982
        elif "紫薯" in input_str:
            max_index = 622
        elif "红豆" in input_str:
            max_index = 1200
        elif input_str == '龙利鱼':
            max_index = 2071
        elif input_str == '龙利鱼柳':
            max_index = 2071
        elif '巴沙鱼' in input_str:
            max_index = 2071
        elif "指天椒" in input_str:
            max_index = 1276
        elif "肥牛" in input_str:
            max_index = 1801
        elif "青菜" in input_str:
            max_index = 1329
        elif "客家娘酒" in input_str:
            max_index = 930
        elif "花生酱" in input_str:
            max_index = 1061
        elif "辽参" in input_str:
            max_index = 695
        elif "猪油" in input_str:
            max_index = 1013
        elif "玉菇" in input_str:
            max_index = 510
        elif "海鲜菇" in input_str:
            max_index = 510
        elif "豌豆" in input_str:
            max_index = 303
        elif "主食" in input_str:
            max_index = 530
        elif "蔬菜" in input_str:
            max_index = 229
        elif "有机菜" in input_str:
            max_index = 229
        elif "肉类" in input_str:
            max_index = 1771
        elif "宫爆酱" in input_str:
            max_index = 1065
        elif input_str == '前腿瘦肉':
            max_index = 1724
        elif input_str == '猪前腿':
            max_index = 1724
        elif input_str == '瘦肉':
            max_index = 1725
        elif "十三香" in input_str:
            max_index = 1133
        elif "酱油" in input_str:
            max_index = 294
        elif "辅食油" in input_str:
            max_index = 1036
        elif "培根" in input_str:
            max_index = 1754
        elif "坚果" in input_str:
            max_index = 1669
        elif "果蔬粉" in input_str:
            max_index = 151
        elif "水果" in input_str:
            max_index = 82
        elif "马斯卡彭" in input_str:
            max_index = 1956
        elif "茶油" in input_str:
            max_index = 1017
        elif "白胡椒" in input_str:
            max_index = 1125
        elif "水饴" in input_str:
            max_index = 976
        elif "樱桃" in input_str:
            max_index = 1585
        elif "油炸面" in input_str:
            max_index = 814
        elif "覆盆子" in input_str:
            max_index = 464
        elif "淀粉" in input_str:
            max_index = 2105
        elif '红薯淀粉' in input_str:
            max_index = 2061
        elif '地瓜淀粉' in input_str:
            max_index = 2061
        elif "青柠" in input_str:
            max_index = 1629
        elif "花胶" in input_str:
            max_index = 1127
        elif "捞汁" in input_str:
            max_index = 158
        elif "花甲" in input_str:
            max_index = 2122
        elif "柱侯酱" in input_str:
            max_index = 1057
        elif "里脊肉" in input_str:
            max_index = 1721
        elif "鱼露" in input_str:
            max_index = 2078
        elif "黄椒" in input_str:
            max_index = 318
        elif "鸡粉" in input_str:
            max_index = 386
        elif "猪骨" in input_str:
            max_index = 1730
        elif "树菇" in input_str:
            max_index = 1458
        elif "娃娃菜" in input_str:
            max_index = 1333
        elif "火鸡面" in input_str:
            max_index = 814
        elif "泡面" in input_str:
            max_index = 814
        elif input_str == '面':
            max_index = 285
        elif '辣鲜露' in input_str:
            max_index = 1043
        elif '昆布' in input_str:
            max_index = 1481
        elif '木鱼花' in input_str:
            max_index = 2210
        elif '云吞' in input_str:
            max_index = 319
        elif '小米椒' in input_str:
            max_index = 1276
        elif '小米辣' in input_str:
            max_index = 1276
        elif '宝宝面' in input_str:
            max_index = 804
        elif '清酒' in input_str:
            max_index = 933
        elif '巴马干酪粉' in input_str:
            max_index = 1953
        elif '三文鱼' in input_str:
            max_index = 2063
        elif '水煮蛋' in input_str:
            max_index = 1976
        elif '香干' in input_str:
            max_index = 393
        elif '油麦菜' in input_str:
            max_index = 209
        elif '油泡' in input_str:
            max_index = 1350
        elif '味极鲜' in input_str:
            max_index = 1047
        elif '酸辣汁' in input_str:
            max_index = 1025
        elif '抹茶' in input_str:
            max_index = 129
        elif '馄饨皮' in input_str:
            max_index = 643
        elif '饺子皮' in input_str:
            max_index = 643
        elif '炼奶' in input_str:
            max_index = 1973
        elif '炼乳' in input_str:
            max_index = 1973
        elif '碗豆' in input_str:
            max_index = 303
        elif '红薯' in input_str:
            max_index = 2
        elif '花生米' in input_str:
            max_index = 1699
        elif '花生仁' in input_str:
            max_index = 1699
        elif '花生碎' in input_str:
            max_index = 1699
        elif input_str == '鸡蛋':
            max_index = 1976
        elif input_str == '苹果':
            max_index = 1487
        elif '羊腰' in input_str:
            max_index = 1842
        elif '羊腩' in input_str:
            max_index = 1830
        elif '马苏里拉' in input_str:
            max_index = 1953
        elif '调味酱' == input_str:
            max_index = 1073
        elif '河粉' in input_str:
            max_index = 716
        elif '瑶柱' in input_str:
            max_index = 2117
        elif '皮蛋' in input_str:
            max_index = 1991
        elif '鸡毛菜' in input_str:
            max_index = 1333
        elif '圣女果' in input_str:
            max_index = 213
        elif '樱桃番茄' in input_str:
            max_index = 213
        elif '梅肉' in input_str:
            max_index = 1720
        elif '辣椒面' in input_str:
            max_index = 1131
        elif '虾滑' in input_str:
            max_index = 2097
        elif '海米' in input_str:
            max_index = 2097
        elif '热油' in input_str:
            max_index = 1016
        elif '香油' in input_str:
            max_index = 1034
        elif '松鲜鲜' in input_str:
            max_index = 1042
        elif '松茸鲜' in input_str:
            max_index = 1042
        elif '碧根果' in input_str:
            max_index = 1673
        elif '果仁' in input_str:
            max_index = 1682
        elif '番鸭' in input_str:
            max_index = 1893
        elif '卷饼' in input_str:
            max_index = 1262
        elif '起司' in input_str:
            max_index = 1953
        elif '起酥' in input_str:
            max_index = 802
        elif '贝贝' in input_str:
            max_index = 661
        elif '线椒' in input_str:
            max_index = 313
        elif '紅椒' in input_str:
            max_index = 1276
        elif '六月鲜' in input_str:
            max_index = 294
        elif '调料' in input_str:
            max_index = 2192
        elif '泡姜' in input_str:
            max_index = 143
        elif '笋片' in input_str:
            max_index = 40
        elif '鸭腿' in input_str:
            max_index = 1893
        elif '鸭架' in input_str:
            max_index = 1915
        elif '鸭骨' in input_str:
            max_index = 1915
        elif '甜辣酱' in input_str:
            max_index = 1068
        elif '南乳' in input_str:
            max_index = 1085
        elif '鸡头米' in input_str:
            max_index = 1714
        elif '莲蓬' in input_str:
            max_index = 1703
        elif '桂花酱' in input_str:
            max_index = 1074
        elif '闸蟹' in input_str:
            max_index = 2100
        elif '蟹味菇' in input_str:
            max_index = 1458
        elif '菌菇' in input_str:
            max_index = 1459
        elif '银牙' in input_str:  # 绿豆芽
            max_index = 1265
        elif '牛腩' in input_str:
            max_index = 1795
        elif '滚油' in input_str:
            max_index = 1022
        elif '无盐黄油' in input_str:
            max_index = 1968
        elif '九层塔' in input_str:
            max_index = 12
        elif '甜米酒' in input_str:
            max_index = 933
        elif '鲍汁' in input_str:
            max_index = 158
        elif '青衣' in input_str:
            max_index = 2014
        elif '日本豆腐' in input_str:
            max_index = 480
        elif '大头鱼' in input_str:
            max_index = 2030
        elif '鱼头' in input_str:
            max_index = 2030
        elif '虎头鱼' in input_str:
            max_index = 2060
        elif '梭鱼' in input_str:
            max_index = 2053
        elif '牛杂' in input_str:
            max_index = 1793
        elif '薑' in input_str:
            max_index = 683
        elif '醬油' in input_str:
            max_index = 294
        elif '奶茶' in input_str:
            max_index = 872
        elif '面团' in input_str:
            max_index = 596
        elif '片糖' in input_str:
            max_index = 974
        elif '蛋黄液' in input_str:
            max_index = 1982
        elif '配方奶' in input_str:
            max_index = 708
        elif '碱' in input_str:
            max_index = 2167
        elif '红薯粉' in input_str:
            max_index = 2061
        elif '剁椒' in input_str:
            max_index = 1064
        elif '鲜虾' in input_str:
            max_index = 2088
        elif '鱼肉' in input_str:
            max_index = 2000
        elif '鱼块' in input_str:
            max_index = 2000
        elif '法棍' in input_str:
            max_index = 819
        elif '香豆' == input_str:
            max_index = 1130
        elif '猪肉馅' in input_str:
            max_index = 1715
        elif '花蜜' in input_str:
            max_index = 977
        elif '排骨' in input_str:
            max_index = 1730
        elif '西红柿酱' in input_str:
            max_index = 1075
        elif '番茄沙司' in input_str:
            max_index = 1075
        elif '牛肋' in input_str:
            max_index = 2189
        elif '南德' in input_str:
            max_index = 2192
        elif '茉莉' in input_str:
            max_index = 879
        elif '泰椒' in input_str:
            max_index = 1276
        elif '阳光玫瑰' in input_str:
            max_index = 1591
        elif '香槟' in input_str:
            max_index = 926
        elif '酒酿' in input_str:
            max_index = 933
        elif '柚子醋' in input_str:
            max_index = 1048
        elif '黄芪' in input_str:
            max_index = 2162
        elif '伏苓' in input_str:
            max_index = 2209
        elif '鸡汁' in input_str:
            max_index = 145
        elif '茶干' in input_str:
            max_index = 1115
        elif '叉烧酱' in input_str:
            max_index = 158
        elif '红烧汁' in input_str:
            max_index = 1039
        elif '朝天椒' in input_str:
            max_index = 1276
        elif '二荆条' in input_str:
            max_index = 313
        elif '白灼' in input_str:
            max_index = 158
        elif '龙眼' in input_str:
            max_index = 1635
        elif '高汤' in input_str:
            max_index = 1891
        elif '羊棒骨' in input_str:
            max_index = 1822
        elif '黑虎虾' in input_str:
            max_index = 2080
        elif '青瓜' in input_str:
            max_index = 334
        elif '羊蝎' in input_str:
            max_index = 2194
        elif '肋排' in input_str:
            max_index = 1730
        elif '鸡脚' in input_str:
            max_index = 1879
        elif '番薯' in input_str:
            max_index = 622
        elif '护心肉' in input_str:
            max_index = 1720
        elif '琵琶腿' in input_str:
            max_index = 1878
        elif '麻婆豆腐调料' in input_str:
            max_index = 1058
        elif '肉馅' == input_str:
            max_index = 1715
        elif '螺丝椒' in input_str:
            max_index = 313
        elif '珍珠米' in input_str:
            max_index = 48
        elif '青口' in input_str:
            max_index = 2120
        elif '坑椒' in input_str:
            max_index = 313
        elif '杭椒' in input_str:
            max_index = 313
        elif '上海青' in input_str:
            max_index = 1342
        elif '红菜椒' in input_str:
            max_index = 314
        elif '淮山' in input_str:
            max_index = 673
        elif '山楂' in input_str:
            max_index = 1540
        elif '乌鱼' in input_str:
            max_index = 2015
        elif '翅尖' in input_str:
            max_index = 1877
        elif '圆葱' in input_str:
            max_index = 144
        elif '话梅' in input_str:
            max_index = 1000
        elif '菜心' in input_str:
            max_index = 1334
        elif '凤梨' in input_str:
            max_index = 1631
        elif '耗油' in input_str:
            max_index = 2178
        elif '卤牛肉' in input_str:
            max_index = 1815
        elif '空心菜' in input_str:
            max_index = 498
        elif '板栗' in input_str:
            max_index = 1674
        elif '蒜末' in input_str:
            max_index = 536
        elif '蒜叶' in input_str:
            max_index = 1310
        elif '大蒜' in input_str:
            max_index = 536
        elif '菊苣' in input_str:
            max_index = 1397
        elif '苦苣' in input_str:
            max_index = 1397
        elif '干辣椒' in input_str:
            max_index = 1275
        elif '干红辣椒' in input_str:
            max_index = 1275
        elif '豆泡' in input_str:
            max_index = 993
        elif '鸡粉' in input_str:
            max_index = 386
        elif '麻椒' in input_str:
            max_index = 1127
        elif '蒜蓉' == input_str:
            max_index = 536
        elif '花雕酒' in input_str:
            max_index = 930
        elif '绿椒' in input_str:
            max_index = 1277
        elif '二层肉' in input_str:
            max_index = 1720
        elif '味素' in input_str:
            max_index = 1140
        elif '鸭翼' in input_str:
            max_index = 1899
        elif '鸭爪' in input_str:
            max_index = 1900
        elif '鸡翼' in input_str:
            max_index = 1877
        elif '鸡掌' in input_str:
            max_index = 1879
        elif '珍珠鸡' in input_str:
            max_index = 1868
        elif '洋白菜' in input_str:
            max_index = 603
        elif '肉片' == input_str:
            max_index = 1725
        elif '肥肠' in input_str:
            max_index = 1729
        elif '芫荽' in input_str:
            max_index = 1372
        elif '猪脚' in input_str:
            max_index = 1732
        elif '底油' in input_str:
            max_index = 1022
        elif '脑花' in input_str:
            max_index = 1742
        elif '笋子' in input_str:
            max_index = 1383
        elif '闸蟹' in input_str:
            max_index = 2100
        elif '鹅油' in input_str:
            max_index = 1010
        elif '明油' in input_str:
            max_index = 1034
        elif '猪腱' in input_str:
            max_index = 1719
        elif '红薯粉' in input_str:
            max_index = 2061



        else:
            input_str_clean = self.remove_brackets(input_str)
            str_list_clean = [ self.remove_brackets(s) for s in str_list]

            # 初始化TF-IDF向量化
            vectorizer = TfidfVectorizer(analyzer='char')  # 让比较基于词汇而不是字符char

            # 将输入字符串与列表组合并转换为TF-IDF矩阵
            texts = [input_str_clean] + str_list_clean
            tfidf_matrix = vectorizer.fit_transform(texts)

            # 计算输入字符串与列表中每个字符串的余弦相似度
            cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])

            # 找出相似度最高的字符串的索引
            max_index = cosine_sim.argmax()

            # # 输出相似度最高的字符串
            # most_similar_string = str_list[max_index]
        return str_list[max_index], max_index

    def count_yes_nutrients(self,suitable_combinations):
        """计算 'YES:' 后面的营养素种类数量，不包括 'NO:' 部分"""
        nutrients = re.findall(r"([\u4e00-\u9fa5A-Za-z()]+):", suitable_combinations)
        return len(nutrients)

    def extract_data(self,data):
        # 尝试解析为JSON格式
        try:
            # 如果是JSON格式的字符串
            parsed_data = json.loads(data)
            if '"response":' in parsed_data:
                parsed_data = parsed_data["response"]# 'adjusted_ingredients','response','data','ingredients']

            elif '食材名称与用量' in parsed_data:
                parsed_data = parsed_data['食材名称与用量']
            elif '食材用量' in parsed_data:
                parsed_data = parsed_data['食材用量']
            elif '食材' in parsed_data:
                parsed_data = parsed_data['食材']
            elif '食材用量调整' in parsed_data:
                parsed_data = parsed_data['食材用量调整']
            elif '食材用量调整方案' in parsed_data:
                parsed_data = parsed_data['食材用量调整方案']
            elif '食材用量调整建议' in parsed_data:
                parsed_data = parsed_data['食材用量调整建议']
            elif 'adjusted_ingredients' in parsed_data:
                parsed_data = parsed_data['adjusted_ingredients']
            elif 'data' in parsed_data:
                parsed_data = parsed_data['data']
            elif 'ingredients' in parsed_data:
                parsed_data = parsed_data['ingredients']
            elif 'optimized_ingredients' in parsed_data:
                parsed_data = parsed_data['optimized_ingredients']

            elif '"食材名称与用量"' in parsed_data:
                parsed_data = parsed_data['"食材名称与用量"']
            elif '"食材用量"' in parsed_data:
                parsed_data = parsed_data['"食材用量"']
            elif '"食材"' in parsed_data:
                parsed_data = parsed_data['"食材"']
            elif '"食材用量调整"' in parsed_data:
                parsed_data = parsed_data['"食材用量调整"']
            elif '"食材用量调整方案"' in parsed_data:
                parsed_data = parsed_data['"食材用量调整方案"']
            elif '"食材用量调整建议"' in parsed_data:
                parsed_data = parsed_data['"食材用量调整建议"']
            elif '"adjusted_ingredients"' in parsed_data:
                parsed_data = parsed_data['"adjusted_ingredients"']
            elif '"data"' in parsed_data:
                parsed_data = parsed_data['"data"']
            elif '"ingredients"' in parsed_data:
                parsed_data = parsed_data['"ingredients"']
            elif '"optimized_ingredients"' in parsed_data:
                parsed_data = parsed_data['"optimized_ingredients"']

            # 返回字典中的内容，按原始顺序构建一个类似字符串的表示
            result = ", ".join([f'"{key}": {value}' for key, value in parsed_data.items()])
            result = re.sub(r'"([^"]+)":', r'\1:', result)  # 去除键名中的双引号
            return result
        except json.JSONDecodeError:
            # 如果解析失败，可能是双引号内的数据
            match = re.search(r'"(.*?)"', data)  # 匹配双引号中的内容
            if match:
                return match.group(1)  # 提取匹配到的内容
            else:
                return "无法提取数据"

    #-> None 是函数返回值的类型注解
    def process_query(self, query: str,target_nutrients,yes_number0):#处理用户输入的查询。
        """
        Process user query

        Args:
            query: User query
        """
        self.last_query = query
        start_time = time.time()
        rate =-1

        try:
            result = self.assistant.get_response(
                query=query,
                conversation_id=self.conversation_id,
                user_info=self.user_info,
                model_name=self.model_name,
                system_prompt=self.system_prompt
            )#调用 self.assistant.get_response() 获取助手的响应。
            print(result)
            #response_text = result.get("response","").strip() #gemma3:27b使用这个
            response_text = result.get("response", "").strip()  # 如果 "response" 键不存在，则返回空字符串 ""，这是 get 方法的第二个参数，作为默认值。
            print("interactive.py正常回答"+response_text)

            #interactive.py正常回答的response_text{
             # "response": "豆腐(内脂): 500.0克,鸡蛋: 70.0克,香菜: 15.0克,火腿: 80.0克,猪肉(瘦): 100.0克,玉米淀粉: 30.0克,精盐: 1.5克,花生油: 2.0克",
             # "status": "success"
             #    }
            #只有当 response_text 非空，且其中“不包含任何英文字符”时才执行 if 语句块。
            #if response_text and not re.search(r'[a-zA-Z]', response_text):
            if response_text:
                # 查找所有英文单词或字母组合
                english_words = re.findall(r'[a-zA-Z]+(?:\([^\)]*\))?', response_text)

                # 如果存在英文，并且去掉允许的 'FritoLay(杂粮小吃)' 后还有其它英文内容，则非法
                #filtered = [word for word in english_words if word != 'FritoLay(杂粮小吃)']
                filtered = [word for word in english_words if word not in ['FritoLay(杂粮小吃)', 'adjusted_ingredients','response','data','ingredients','optimized_ingredients']]

                if not filtered:
                    response_text_data = self.extract_data(response_text)
                    print("response_text有内容")
                    ingredients_response_text = response_text_data.split(',')
                    # 创建一个新列表来保存修改后的食材
                    updated_response_text = []
                    # 检查每个食材并修改
                    for ingredient in ingredients_response_text:
                        # 去除两端空白字符
                        ingredient = ingredient.strip()
                        # 如果食材不以 "克" 结尾，添加 "克"
                        if not ingredient.endswith("克"):
                            ingredient += "克"
                        # 将修改后的食材加入列表
                        updated_response_text.append(ingredient)

                    # 将更新后的食材列表重新拼接成字符串
                    response_text2 = ",".join(updated_response_text)
                    # 替换原来的 "response" 内容
                    data_response_text={}
                    data_response_text['response'] = response_text2
                    data_response_text['status'] = "success"

                    # 将修改后的字典重新转换为 JSON 字符串
                    response_text = json.dumps(data_response_text, ensure_ascii=False)

            print(response_text)
            model_used = result.get("model_used", "")
            completion_time = result.get("completion_time", 0)

            # Display the response
            print(f"\nAssistant ({model_used}, {completion_time:.2f}s): {response_text}")

            # 解析 JSON
            response_text_data = json.loads(response_text)

            # 获取 "response" 的值
            response_text_data_value = response_text_data.get("response", "")#'豇豆: 100.0克，熟虾仁: 50.0克，四川宫爆酱: 10.0克，盐: 2.0克，糖: 10.0克'
            ingredients_list = response_text_data_value.split(',')
            # 初始化结果列表
            ingredients = []
            # 遍历每一个食材信息
            for item in ingredients_list:
                # 去除多余空格，并按冒号分割
                name, amount = re.split(r':|：|: |： ', item.strip())
                try:
                    # name, amount = item.strip().split(':')
                    # 去除单位并转换为整数
                    amount = float(amount.replace('克.', '').replace('克', '').replace('g', '').strip())
                except:
                    amount=amount
                # 添加为元组到结果列表
                if "水" not in name and "冰块" not in name and "白开" not in name:
                    ingredients.append((name.strip(), amount))
            #print(ingredients)
            # Calculate total nutrients
            nutrition_df = self.load_nutrition_data('C:\\code\\zjcode\deepseekrecipe\\file\\19_nutritional_data.xlsx')
            nutrient_sums,matched_ings,new_recipe = self.calculate_nutrients(ingredients, nutrition_df)
            suitability, yes, no = self.check_suitability(nutrient_sums, target_nutrients)
            if yes:
                yes_number = self.count_yes_nutrients(yes)  # 原食谱中符合的
            else:
                yes_number =0
            if yes_number>yes_number0:
                rate = int(yes_number - yes_number0)
                #rate=int(yes_number/((19-yes_number0)/5))
            else:
                rate=-1

            # Check if feedback should be requested打分与反馈
            self._maybe_ask_for_feedback(rate)#如果需要，调用 self._maybe_ask_for_feedback() 请求用户反馈。

        except KeyboardInterrupt:
            print("\nRequest canceled.")
        except Exception as e:

            #{'response': '', 'conversation_id': 'conv_1742341404', 'completion_time': 0.7817873954772949, 'model_used': 'gemma3:27b', 'optimized': False, 'auto_model_selection': {}, 'group_discussion': {}, 'query_analysis': {}}
            print('result = self.assistant.get_response非正常调用')

            response_text_data_value=""



        # Display total time
        total_time = time.time() - start_time
        if total_time > 0.5:  # Only display if it took a long time
            print(f"(Completed in {total_time:.2f}s)")

        return rate,response_text_data_value

    def _maybe_ask_for_feedback(self,rate) -> None:#根据条件请求用户对助手的响应进行评分和评论。
        """Request feedback from the user if conditions are met"""
        if not self.assistant.feedback_collection_enabled:#检查反馈收集功能是否启用
            return

        # Determine whether to request feedback (logic from FeedbackCollector)
        # try:
        #     should_ask = self.assistant.feedback_manager.feedback_collector.should_request_feedback(
        #         self.conversation_id)
        #     #如果 self.assistant.feedback_manager.feedback_collector 对象有 should_request_feedback 方法，则调用该方法决定是否请求反馈。
        # except AttributeError:
        #     # If there is no should_request_feedback method, use random probability
        #     import random
        #     should_ask = random.random() < 0.3#使用随机概率决定是否请求反馈。
        should_ask=True
        if should_ask:
            try:
                # print("\n--- Feedback ---")
                # print("How would you rate this response? (1-5, or skip)")
                #打分
                rating =str(rate) #input("Rating: ").strip()#通过键盘输入

                if rating:# and rating in "12345":
                    #score = float(rating) / 5.0#如果用户输入有效（1-5），则将评分转换为 0 到 1 之间的浮点数
                    score = float(rating)
                    #print("Do you have any additional comments? (Press Enter to skip)")
                    feedback_text =''#input("Comments: ").strip()

                    # Get the last response
                    history = self.assistant.get_conversation_history()#获取会话历史
                    if history and len(history) >= 2:
                        last_response = history[-1].get("content", "")#如果会话历史存在且长度大于等于 2，则获取最后一次助手的响应内容

                        # Save feedback
                        self.assistant.provide_feedback(
                            query=self.last_query,
                            selected_response=last_response,
                            feedback_score=score,
                            feedback_text=feedback_text if feedback_text else None
                        )#将用户反馈（评分和评论）保存到系统中。

                        print("Thank you for your feedback!")

            except KeyboardInterrupt:
                print("\nFeedback skipped.")
            except Exception as e:
                logger.error(f"Error collecting feedback: {e}")

    def do_exit(self, arg: str) -> bool:#退出交互式命令行界面。
        """
        Exit the interactive shell

        Args:
            arg: Argument (not used)

        Returns:
            True to end the loop
        """
        print("Goodbye!")
        return True

    def do_quit(self, arg: str) -> bool:#作用：exit 的别名，功能与 do_exit 相同。
        """Alias for exit"""
        return self.do_exit(arg)

    def do_bye(self, arg: str) -> bool:#作用：exit 的别名，功能与 do_exit 相同。
        """Alias for exit"""
        return self.do_exit(arg)

    def do_clear(self, arg: str) -> None:#清屏并开始一个新的会话。
        """
        Clear the screen and start a new conversation

        Args:
            arg: Argument (not used)
        """
        # Clear the screen
        os.system('cls' if os.name == 'nt' else 'clear')#清空屏幕

        # Initialize a new conversation
        self.assistant.clear_conversation()#初始化一个新的会话 ID。
        self.conversation_id = f"conv_{int(time.time())}"#重新显示介绍信息和状态。

        # Display the intro again
        print(self.intro)
        self._update_status_display()
        print(f"Status: {self.status}")

        print("Cleared conversation and started a new one.")

    def do_status(self, arg: str) -> None:#显示当前系统的详细状态。
        """
        Display current status

        Args:
            arg: Argument (not used)
        """
        self._update_status_display()#调用 self._update_status_display() 更新状态。
        print(f"Status: {self.status}")

        # Display detailed information显示当前会话 ID、反馈样本数量、当前模型等信息。
        stats = self.assistant.get_stats()
        optimization = stats.get("optimization", {})

        print("\nDetailed Information:")
        print(f"- Current Conversation: {self.conversation_id}")
        print(f"- Total Feedback Samples Collected: {optimization.get('feedback_collection', {}).get('total_samples', 0)}")

        if self.model_name:
            print(f"- Current Model: {self.model_name}")

        # Display model weights if available
        model_weights = optimization.get("model_weights", {})
        if model_weights:
            print("\nModel Weights:")
            for model, weight in model_weights.items():
                print(f"- {model}: {weight:.2f}")

    def do_model(self, arg: str) -> None:#设置或显示当前使用的模型。
        """
        Set or display the current model

        Args:
            arg: Model name to set
        """
        if not arg:#如果未提供参数，则显示当前模型和可用模型列表。
            available_models = []
            try:
                available_models = self.assistant.model_manager.list_models()
            except:
                # Get the list of models through EnhancedPersonalAssistant
                pass

            print(f"Current Model: {self.model_name or 'auto'}")
            if available_models:
                print(f"Available Models: {', '.join(available_models)}")
            return

        arg = arg.strip()
        if arg == "auto":#启用自动模型选择
            self.model_name = None
            self.assistant.toggle_auto_select_model(True)
            print("Switched to auto model selection mode.")
        else:#切换到指定模型
            available_models = []
            try:
                available_models = self.assistant.model_manager.list_models()
            except:
                # Try another way to get the list of models
                try:
                    available_models = [m.get("name") for m in self.assistant.config.get("models", [])]
                except:
                    pass

            if arg in available_models:
                self.model_name = arg
                print(f"Switched to model: {arg}")
            else:
                print(f"Error: Model '{arg}' does not exist.")
                if available_models:
                    print(f"Available Models: {', '.join(available_models)}")

        self._update_status_display()

    def do_toggle(self, arg: str) -> None:#切换系统功能的开关状态。
        """
        Toggle features on/off

        Args:
            arg: Feature name (optimization, feedback, auto-model, group-discussion)
        """
        valid_features = ["optimization", "feedback", "auto-model", "group-discussion"]

        if not arg or arg.strip() not in valid_features:
            print(f"Syntax: toggle <feature>")
            print(f"Available Features: {', '.join(valid_features)}")
            return

        feature = arg.strip()
        #根据用户输入的功能名称（如 optimization、feedback 等），切换相应的功能状态。
        if feature == "optimization":
            new_state = not self.assistant.optimization_enabled
            self.assistant.toggle_optimization(new_state)
            print(f"Optimization: {'ON' if new_state else 'OFF'}")

        elif feature == "feedback":
            new_state = not self.assistant.feedback_collection_enabled
            self.assistant.toggle_feedback_collection(new_state)
            print(f"Feedback Collection: {'ON' if new_state else 'OFF'}")

        elif feature == "auto-model":
            new_state = not self.assistant.auto_select_model
            self.assistant.toggle_auto_select_model(new_state)
            print(f"Auto Model Selection: {'ON' if new_state else 'OFF'}")

        elif feature == "group-discussion":
            new_state = not self.assistant.use_group_discussion
            self.assistant.toggle_group_discussion(new_state)
            print(f"Group Discussion: {'ON' if new_state else 'OFF'}")

        self._update_status_display()

    def do_system(self, arg: str) -> None:#设置或显示系统提示（system prompt）。
        """
        Set or display the system prompt

        Args:
            arg: New system prompt
        """
        if not arg:#如果未提供参数，则显示当前系统提示。
            print(f"Current System Prompt: {self.system_prompt or 'Default'}")
            return

        self.system_prompt = arg.strip()#如果提供了参数，则设置新的系统提示。
        print(f"Set new system prompt.")

    def do_user(self, arg: str) -> None:#设置或显示用户信息。
        """
        Set user information

        Args:
            arg: User information in JSON format
        """
        if not arg:#如果未提供参数，则显示当前用户信息。
            print(f"Current User Information: {json.dumps(self.user_info, ensure_ascii=False) if self.user_info else 'None'}")
            return

        try:#如果提供了参数，则解析 JSON 格式的用户信息并保存。
            self.user_info = json.loads(arg.strip())
            print(f"Set new user information.")
        except json.JSONDecodeError:
            print("Error: Information is not in valid JSON format.")

    def do_export(self, arg: str) -> None:#导出反馈数据。
        """
        Export feedback data

        Args:
            arg: Export directory (optional)
        """
        export_dir = arg.strip() if arg else None

        try:
            export_path = self.assistant.export_feedback_data(export_dir)
            if export_path:#如果提供了导出目录，则将反馈数据导出到指定目录。
                print(f"Exported feedback data to: {export_path}")
            else:#如果未提供目录，则使用默认目录。
                print("Failed to export feedback data.")
        except Exception as e:
            print(f"Error exporting data: {e}")

    def do_help(self, arg: str) -> None:#：显示帮助信息。
        """
        Display help

        Args:
            arg: Command name for help
        """
        if not arg:
            print("\nAvailable Commands:")
            print("  status        - Display current status")
            print("  model [name]  - Set or display the model ('auto' for auto selection)")
            print("  toggle <opt>  - Toggle features (optimization, feedback, auto-model, group-discussion)")
            print("  system [text] - Set or display the system prompt")
            print("  user [json]   - Set or display user information")
            print("  export [dir]  - Export feedback data")
            print("  clear         - Clear the screen and start a new conversation")
            print("  exit/quit     - Exit the program")
            print("\nType your query directly to interact with the assistant.")
            return

        super().do_help(arg)

    def run(self) -> None:#启动交互式命令行界面。
        """Run the interactive shell"""
        self._update_status_display()#调用 self._update_status_display() 更新状态。
        print(f"Status: {self.status}")#Status: Optimization: ON | Feedback Collection: ON | Auto Model Selection: ON | Group Discussion: OFF

        try:
            self.cmdloop()#cmdloop() 是 cmd.Cmd 类（Python 标准库）的一个方法，用于运行一个简单的命令行循环。
            #self.cmdloop()后prompt = "\nYou: "后调用default函数
        except KeyboardInterrupt:#如果用户按下 Ctrl+C（触发 KeyboardInterrupt 异常），则捕获该异常并打印退出信息。
            print("\nReceived interrupt signal, exiting...")
        except Exception as e:
            logger.error(f"Unexpected error in shell: {e}")
            print(f"\nAn error occurred: {e}")
        finally:
            print("Goodbye!")