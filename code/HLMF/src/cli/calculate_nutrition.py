import pandas as pd#这个用于构建chatgpt回答一次后不同年龄段、性别、劳动程度的所有食谱营养素是否符合的csv
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from deep_translator import MyMemoryTranslator
from opencc import OpenCC
from openai import OpenAI
converter = OpenCC('t2s')
# Convert Traditional Chinese to Simplified Chinese

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key="sk-uyvPytD7VFywQ6FR5fcVDAztrKkmqswMjh14olYOh73PFT1x",
    base_url="https://api.chatanywhere.tech/v1"#国内
)#"https://api.chatanywhere.org/v1"#国外
#"https://api.chatanywhere.tech/v1"#api_key="sk-vbz77oUE6tzLmBTZWGNyEcwPvrHs2b5moaYUWsm7i6fL4Ly5",免费
#"sk-uyvPytD7VFywQ6FR5fcVDAztrKkmqswMjh14olYOh73PFT1x",收费
# 读取食谱和化合物数据
# recipes_df = pd.read_csv('./file/recipe300.csv')
# flavordb_df = pd.read_csv('./file/flavordb_new.csv')

def find_best_match(target, series):
    #print(target)
    # for x in series:
    #     a=set(x.strip('{}').split(', '))
    #     print(set(x.strip('{}').split(', ')))
    # 计算相似度
    matches = series.apply(lambda x: len(target.intersection(set(x.strip('{}').split(', ')))) / len(
        set(x.strip('{}').split(', '))) if len(set(x.strip('{}').split(', '))) > 0 else 0)

    # 找到相似度最高的ID
    best_ids = matches[matches == 1].index.tolist()
    return best_ids

def convert_to_simplified(text):
    cc = OpenCC('t2s')
    return cc.convert(text)

# 定义保存结果到 CSV 的函数
def save_results_to_csv(results, file_path='./results2.csv'):
    # 创建用于保存结果的列表
    output_data = []

    # 处理每个结果
    for result in results:
        index = result['index']
        ingredients = result['ingredients']
        suitable_combinations = result['suitable_combinations']

        # 将 suitable_combinations 转换为字符串
        suitable_combinations_str = "; ".join([f" {age_range}_{gender}_{pal},YES: {yes}, NO: {no}" for age_range, gender, pal,yes,no in suitable_combinations])

        # 创建一行数据
        row_data = {
            'index': index,
            'nutrient_sums': ingredients,
            'suitable_combinations': suitable_combinations_str
        }

        # 添加到输出数据中
        output_data.append(row_data)

    # 转换为 DataFrame
    df = pd.DataFrame(output_data)

    # 保存为 CSV 文件
    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"结果已保存到 {file_path}")


def chinese_to_arabic(chinese_num):
    cn2an = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
             '百': 100, '千': 1000, '万': 10000, '亿': 100000000, '半': 0.5}
    if chinese_num == '半':
        return 0.5
    total = 0
    unit = 1
    for character in reversed(chinese_num):
        if character in cn2an:
            num = cn2an[character]
            if num >= 10 and num > unit:
                unit = num
            else:
                total += num * unit
        else:
            unit = 1
    return total


# Function to replace Chinese numbers, excluding special words
def replace_chinese_number(match):
    word = match.group()
    return str(chinese_to_arabic(word))


# Protect specific words by marking them
def protect_special_words(text):
    special_words = ['五香粉', '五香','八角','五花肉','五花']
    for word in special_words:
        text = text.replace(word, f'__{word}__')
    return text


# Restore specific words by removing markers
def restore_special_words(text):
    special_words = ['五香粉', '五香','八角','五花肉','五花']
    for word in special_words:
        text = text.replace(f'__{word}__', word)
    return text

def parse_ingredients(ingredients_str):
    # Remove modifiers after units
    ingredients_list = ingredients_str.split(',')
    # Regular expression to match each ingredient
    pattern = r'([\u4e00-\u9fa5]+(?:[\u4e00-\u9fa5]+)?)[^,\d]*?(\d+(/\d+)?)?(克|g|千克|公斤|个|适量|数粒|两|斤|片|湯匙|茶匙|棵|杯|块|只)(?:[（(](\d+克)[）)])?'

    processed_ingredients = []
    for ingredient_str in ingredients_list:
        match = re.match(pattern, ingredient_str.strip())
        if match:
            name, amount, fraction, unit, parenthesis_amount = match.groups()
            try:
                processed_ingredients.append(
                    (name.strip(), amount + (
                        unit if unit not in ['克', 'g', '千克', '公斤', '个', '适量', '粒', '数粒', '斤', '条', '只', '两', '片', '湯匙',
                                             '茶匙', '杯', '块', '棵'] else ''))
                )
            except:
                continue

    # Convert to expected format and remove duplicates
    final_ingredients = []

    for name, amount in processed_ingredients:
        name = name.strip()
        if name in ('请注意','水','栀子','凉白开','冷水','荷叶','黄桅子','烘焙碱','视水','枧水','矿泉水','开水','冷开水','冷开水温开水','温水','凉水','凉开水','热水','温开水','冰水','清水','纯净水','常温水','泡椒水','明胶用水','家里食材随心搭配','苏打','小苏打','食用小苏打','苏打粉'):
            continue
        try:
            final_ingredients.append((name, int(float(amount))))
        except:
            final_ingredients.append((name, amount))  # Retain original format if conversion fails

        print(name.strip(), amount)

    return final_ingredients


def load_nutrition_data(file_path='D:\code\MOBO\zj\\analysis_recipes\\file\\19_nutritional_data.xlsx'):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()  # 去除列名中的空格
    df['食物名称'] = df['食物名称'].str.strip()  # 去除索引中的空格
    #df.set_index('食物名称', inplace=True)
    return df


# Remove brackets and punctuation
def remove_brackets(text):
    text = re.sub(r"（.*?）|\{.*?\}|\[.*?\]|【.*?】", '', text)
    text = re.sub(r"[,;:'\"。，、；：‘’“”]", '', text)
    return text.strip()


# Find the best cosine similarity match
def find_best_cosine_match(input_str, str_list):
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
        input_str_clean = remove_brackets(input_str)
        str_list_clean = [remove_brackets(s) for s in str_list]

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


# Read and match ingredients
def readIngredient(choices):
    ingredients = []
    df = pd.read_excel('D:\code\MOBO\zj\\analysis_recipes\\file\\19_nutritional_data.xlsx')  # All ingredients
    df.columns = df.columns.str.strip()  # 去除列名中的空格
    df['食物名称'] = df['食物名称'].str.strip()  # 去除索引中的空格
    column_names = df.columns.tolist()  # Get column names

    for index, row in df.iterrows():  # Iterate over rows
        row_dict = {col: row[col] for col in column_names}  # Create dictionary
        ingredients.append(row_dict)

    food_names = [item['食物名称'] for item in ingredients]  # Extract food names
    matched = []
    for target_string in choices:
        best_match_name, best_index = find_best_cosine_match(target_string, food_names)  # Find best match
        matched.append(ingredients[best_index])  # Add matched item dictionary
        print(f"对于 '{target_string}', 最佳匹配是: {best_match_name}")

    return matched


# Calculate total nutrient content
def calculate_nutrients(ingredients, nutrition_df):
    nutrition_df.set_index('食物名称', inplace=True)
    matched_ingredients = readIngredient([name for name, weight in ingredients])

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

# 定义处理函数
def subtract_values(target_value, nutrient_value):
    if isinstance(target_value, tuple):
        # 对 tuple 中的每个值分别减去 nutrient_value
        return tuple(t - nutrient_value for t in target_value)
    elif isinstance(target_value, float):
        # 如果是 float，直接相减
        return target_value - nutrient_value
    else:
        return target_value  # 保持原样，如果类型不匹配

# def translate_in_batches(text_list, source_lang='en-US', target_lang='zh-CN', batch_size=5000):
#     translator = MyMemoryTranslator(source=source_lang, target=target_lang)
#     translated_texts = []
#     current_batch = []
#     current_batch_size = 0
#
#     for text in text_list:
#         # 检查当前文本的长度是否超过单次翻译限制
#         if current_batch_size + len(text) < batch_size:
#             current_batch.append(text)
#             current_batch_size += len(text)
#         else:
#             # 当达到限制时，进行翻译
#             translated_texts.append(translator.translate_batch(current_batch))
#             current_batch = [text]
#             current_batch_size = len(text)
#
#     # 翻译剩余的文本
#     if current_batch:
#         translated_texts.append(translator.translate_batch(current_batch))
#
#     return translated_texts

def calculate_reward(nutrients,target_nutrition):
    #df = nutrients - target_nutrition
    # 使用 applymap 和 lambda 函数进行处理
    df = target_nutrition.apply(lambda col: subtract_values(col.iloc[0], nutrients[col.name].iloc[0]), axis=0)
    # 结果
    #print(df)
    # 获取“热量（千卡）”的值
    # 初始化一个空字符串
    result_string = ""

    # 遍历 Series 中的所有元素
    for index, value in df.items():
        if isinstance(value, float):
            # 处理 float 类型的值
            if value > 0:
                result_string += f"{index}需要增加{value:.2f}，"
            else:
                result_string += f"{index}需要减少{-value:.2f}，"
        elif isinstance(value, tuple):
            # 处理 tuple 类型的值，格式化 tuple 的每个元素
            formatted_tuple = f"({value[0]:.2f}, {value[1]:.2f})"
            result_string += f"{index}的添加量在{value[0]:.2f}至{value[1]:.2f}之间，"
            # increases = []
            # decreases = []
            # for v in value:
            #     if v > 0:
            #         increases.append(f"增加{v:.2f}")
            #     else:
            #         decreases.append(f"减少{-v:.2f}至")

    #print(result_string)
    # 替换并格式化字符串
    output_string = re.sub(r'([\u4e00-\u9fa5]+)[（(]([^)）]+)[)）]需要(增加|减少)([\d\.\-]+)', r'\1需要\3\4\2', result_string)
    output_string = re.sub(
        r'([\u4e00-\u9fa5A-Za-z]+)[（\(]([^\)）]+)[\)）]的添加量在([-\d\.]+)至([-\d\.]+)之间',
        r'\1的添加量在\3\2至\4\2之间',
        output_string
    )
    output_string=output_string.rstrip('，')
    print(output_string)


    return output_string

def gpt_35_api(messages: list):
    """为提供的对话消息创建新的回答

    Args:
        messages (list): 完整的对话消息
        免费版支持gpt-3.5-turbo, embedding, gpt-4o-mini, gpt-4
    """
    completion = client.chat.completions.create(model="o3-mini", messages=messages)#gpt-3.5-turbo
    #print(completion.choices[0].message.content)
    return completion.choices[0].message.content

def initialize_conversation(nutrition_df):
    """
    初始化对话，设置基本的系统和背景信息。
    """
    message_content0 = f"该表格包含 {len(nutrition_df)} 种食材，每种食材重量为100克时的营养素含量。请根据该表格中提供的食材信息，完成接下来我给你布置的任务。"

    messages = [
        {'role': 'system', 'content': '你是一个注册营养师。'},
        {'role': 'user', 'content': message_content0},
        {'role': 'assistant', 'content': '我已理解该表格，请提出任务。'}
    ]
    return messages

# 记录每个食谱包括的所有化合物
recipe_compounds = {}
def adjust_recipe(recipe, target_nutrition, matched_ing,nutrients,nutrition_df):#, max, min,result_all):
    # 检查是否包含 "馒头" 或 "米饭"
    # contains_mantou_or_rice = any(item['食物名称'] in ['馒头', '米饭'] for item in matched_ing)
    # # 输出结果
    # # for index, row in nutrition_df.iterrows():
    # #     print(index)
    # #     print(row.values.tolist())
    #      # 按列名访问每行数据
    # if not contains_mantou_or_rice:
    #     for index, row in nutrition_df.iterrows():
    #         if row['食物名称'] in ['馒头', '米饭']:
    #             matched_ing.append(row.to_dict())
    food_names = [item['食物名称'] for item in matched_ing]
    print(food_names)
    print('旧食谱是'+recipe)
    #reward = calculate_reward(nutrients,target_nutrition)

    # 只考虑原食材、米饭、馒头
    message_content = (
        f"请根据每100g不同食材的营养素数据表格{matched_ing}优化食谱{recipe}，满足目标营养素要求{target_nutrition}。"
        f"不改变食谱{recipe}中的食材名称，仅优化食材用量(食材用量是包括0在内的小数)。"
        f"请仅输出食材名称及用量（格式为：“食材名称: 克”。食材之间用‘,’隔开（逗号后无空格）），用量需精确到小数点后一位，不包含任何计算、推理或多余文字。"
    )#str(age_range)+'_男_低_results_gpt1.csv

    # message_content_a = (
    #     f"我有一个旧食谱“{recipe}”，它的营养素总量如表格所示：{nutrients}。"
    #     f"为了使旧食谱“{recipe}“满足目标营养素要求{target_nutrition}，请根据每100g不同食材的营养素数据表格{matched_ing}优化旧食谱“{recipe}“。"
    #     f"旧食谱“{recipe}“的{reward}。"
    #     f"可以删除旧食谱“{recipe}“中的一种或多种食材，或者仅修改食材用量，并且加入馒头或米饭。"
    #     f"请输出新食谱，格式与“{recipe}”的格式相同。输出仅包含食材名称与用量（用量以克为单位），不包含计算、推理等其它多余文字。食材用量用小数表示（精确到小数点后四位）。"
    # )#str(age_range)+'_男_低_results_gpt1_a.csv

    # message_content_b = (
    #     f"我有一个旧食谱“{recipe}”，它的营养素总量如表格所示：{nutrients}。"
    #     f"为了使旧食谱“{recipe}“满足目标营养素要求{target_nutrition}，请根据每100g不同食材的营养素数据表格{matched_ing}优化旧食谱“{recipe}“。"
    #     f"可以删除旧食谱“{recipe}“中的一种或多种食材，或者仅修改食材用量，并且加入馒头或米饭。"
    #     f"请输出新食谱，格式与“{recipe}”的格式相同。输出仅包含食材名称与用量（用量以克为单位），不包含计算、推理等其它多余文字。食材用量用小数表示（精确到小数点后四位）。"
    # )#str(age_range)+'_男_低_results_gpt1_b.csv
    #########系统消息可用于在回复中指定模型所使用的角色。
    messages=[
            {'role': 'system', 'content': '你是一个出色的注册营养师。'},
            {'role': 'user', 'content': message_content}
            ]

    # df = pd.DataFrame(result_all)
    # for index, txt in df.iterrows():#这样追加对？
    #     messages.append({'role': 'system', 'content': txt['食物名称']})
    # messages.append( {'role': 'user', 'content': message_content})

    # 调用 gpt_35_api 函数获取回答
    response = gpt_35_api(messages)
    print('gpt回答:'+response)

    return response

# Check suitability
def check_suitability(nutrient_sums, target_nutrients):#,recipe,matched_ing):
    print(nutrient_sums)
    print(target_nutrients)
    suitability = True
    truenum=0
    falsenum = 0
    yes=''
    no=''
    for i, (key, value) in enumerate(target_nutrients.items()):
        if isinstance(value, float):#没有最大摄入量的营养素怎么考虑？
            tolerance = 0.1 * value
            # # 下限和上限
            lower_bound = value - tolerance
            upper_bound = value + tolerance
            if lower_bound <= nutrient_sums[i] <= upper_bound:
                #suitability = True

                s1=f"{key}: {nutrient_sums[i]}符合,"
                # print(s1)
                yes = yes + s1
            else:
                #suitability = False

                s2=f"{key}: {nutrient_sums[i]}不合适,"
                # print(s2)
                no = no + s2
            #suitability = True

        elif isinstance(value, tuple):
            if value[0] <= nutrient_sums[i] <= value[1]:
                #suitability=True
                s3=f"{key}: {nutrient_sums[i]} within {value},"
                # print(s3)
                yes = yes + s3
            else:
                #suitability=False
                s4=f"{key}: {nutrient_sums[i]} not {value},"
                # print(s4)
                no = no + s4
        # if suitability == False:#有一个营养素不符合要求break
        #     break
    #以下是如果truenum>falsenum，suitability = True
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
    yes=yes.rstrip(',')
    no=no.rstrip(',')
    return suitability,yes,no


def obtain_target(age,gender,pal):
    if 1 <= age < 2:#维生素B1又称硫胺素,维生素B2又叫核黄素,胆固醇又称胆甾醇 2000千卡 × 20% = 400千卡 400千卡 ÷ 9千卡/克 = 约44克
        if gender[0]=="男":
            target_dict = { "热量（千卡）": 900, "硫胺素(毫克)": 0.6, "钙(毫克)": '500-1500',"蛋白质(克)": 25, "核黄素(毫克)": 0.7, "镁(毫克)": 140, "脂肪(克)": 315,  "烟酸(毫克)": '6-11',  "铁(毫克)": '10-25', "碳水化合物(克)": '120-146.3',
                "维生素C(毫克)": '40-400', "锰(毫克)": 2, "膳食纤维(克)": '5-10', "维生素E(毫克)": '6-150', "锌(毫克)": '4-9',  "维生素A(微克)": '340-700', "铜(毫克)": '0.3-2',  "钾(毫克)": 900,  "磷(毫克)": 300,  "钠(毫克)": 500,   "硒(微克)": '25-80'
            }
        else:
            target_dict = {  "热量（千卡）": 800, "硫胺素(毫克)": 0.6, "钙(毫克)": '500-1500', "蛋白质(克)": 25,"核黄素(毫克)": 0.6, "镁(毫克)": 140,"脂肪(克)": 280, "烟酸(毫克)": '5-11', "铁(毫克)": '10-25',"碳水化合物(克)": '120-129.9',
                "维生素C(毫克)": '40-400', "锰(毫克)": 1.5, "膳食纤维(克)": '5-10',"维生素E(毫克)": '6-150', "锌(毫克)": '4-9', "维生素A(微克)": '330-700', "铜(毫克)": '0.3-2',  "钾(毫克)": 900,  "磷(毫克)": 300, "钠(毫克)": 500, "硒(微克)": '25-80'
            }

    elif 2 <= age < 3:#维生素B1又称硫胺素,维生素B2又叫核黄素,胆固醇又称胆甾醇,维生素A（RE）即视黄醇当量没有约束
        if gender[0] == "男":
            target_dict = {"热量（千卡）": 1100,"硫胺素(毫克)": 0.6, "钙(毫克)": '500-1500',"蛋白质(克)": 25, "核黄素(毫克)": 0.7, "镁(毫克)": 140, "脂肪(克)": 385, "烟酸(毫克)": '6-11', "铁(毫克)": '10-25',"碳水化合物(克)": '120-178.6',
                "维生素C(毫克)": '40-400', "锰(毫克)": 2, "膳食纤维(克)": '5-10',"维生素E(毫克)": '6-150',"锌(毫克)": '4-9',"维生素A(微克)": '340-700', "铜(毫克)": '0.3-2',  "钾(毫克)": 900, "磷(毫克)": 300, "钠(毫克)": 600, "硒(微克)": '25-80'
            }
        else:
            target_dict = { "热量（千卡）": 1000, "硫胺素(毫克)": 0.6, "钙(毫克)": '500-1500',"蛋白质(克)": 25, "核黄素(毫克)": 0.6, "镁(毫克)": 140, "脂肪(克)": 350, "烟酸(毫克)": '5-11',"铁(毫克)": '10-25', "碳水化合物(克)": '120-162.2',
                "维生素C(毫克)": '40-400', "锰(毫克)": 1.5, "膳食纤维(克)": '5-10', "维生素E(毫克)": '6-150',"锌(毫克)": '4-9',"维生素A(微克)": '330-700', "铜(毫克)": '0.3-2',"钾(毫克)": 900,  "磷(毫克)": 300, "钠(毫克)": 600, "硒(微克)": '25-80'
            }

    elif 3 <= age < 4:##维生素B1又称硫胺素,维生素B2又叫核黄素,胆固醇又称胆甾醇,维生素A（RE）即视黄醇当量没有约束
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 1250, "硫胺素(毫克)": 0.6, "钙(毫克)": '500-1500',"蛋白质(克)": 30, "核黄素(毫克)": 0.7,"镁(毫克)": 140, "脂肪(克)": 437.5, "烟酸(毫克)": '6-11', "铁(毫克)": '10-25', "碳水化合物(克)": '120-203.0',
                "维生素C(毫克)": '40-400', "锰(毫克)": 2, "膳食纤维(克)": '5-10', "维生素E(毫克)": '6-150', "锌(毫克)": '4-9', "维生素A(微克)": '340-700', "铜(毫克)": '0.3-2', "钾(毫克)": 900, "磷(毫克)": 300, "钠(毫克)": 700, "硒(微克)": '25-80'
            }
        else:
            target_dict = {
                "热量（千卡）": 1250, "硫胺素(毫克)": 0.6,  "钙(毫克)": '500-1500', "蛋白质(克)": 30,"核黄素(毫克)": 0.6,"镁(毫克)": 140, "脂肪(克)": 437.5, "烟酸(毫克)": '5-11', "铁(毫克)": '10-25', "碳水化合物(克)": '120-186.6',
                "维生素C(毫克)": '40-400', "锰(毫克)": 1.5,"膳食纤维(克)": '5-10',"维生素E(毫克)": '6-150',"锌(毫克)": '4-9',"维生素A(微克)": '330-700', "铜(毫克)": '0.3-2', "钾(毫克)": 900, "磷(毫克)": 300, "钠(毫克)": 700, "硒(微克)": '25-80'
            }

    elif 4 <= age < 5:#维生素B1又称硫胺素,维生素B2又叫核黄素,胆固醇又称胆甾醇,维生素A（RE）即视黄醇当量没有约束
        if gender[0] == "男":#数据处理到这里
            target_dict = {
                "热量（千卡）": 1300,"硫胺素(毫克)": 0.9, "钙(毫克)": '600-2000', "蛋白质(克)": '30-65',"核黄素(毫克)": 0.9, "镁(毫克)": 160,"脂肪(克)": '28.89-43.33', "烟酸(毫克)": '7-15', "铁(毫克)": '10-30', "碳水化合物(克)": '162.5-211.25',
                "维生素C(毫克)": '50-600', "锰(毫克)": '2-3.5', "膳食纤维(克)": '10-15',"维生素E(毫克)": '7-200',"锌(毫克)": '5.5-13',"维生素A(微克)": '390-1000', "铜(毫克)": '0.4-3', "钾(毫克)": 1100, "磷(毫克)": 350, "钠(毫克)": 800, "硒(微克)": '30-120'
            }
        else:
            target_dict = {
                "热量（千卡）": 1300,"硫胺素(毫克)": 0.9, "钙(毫克)": '600-2000', "蛋白质(克)": '30-65',"核黄素(毫克)": 0.8, "镁(毫克)": 160,"脂肪(克)": '28.89-43.33', "烟酸(毫克)": '6-15', "铁(毫克)": '10-30', "碳水化合物(克)": '162.5-211.25',
                "维生素C(毫克)": '50-600', "锰(毫克)": '2-3.5', "膳食纤维(克)": '10-15',"维生素E(毫克)": '7-200',"锌(毫克)": '5.5-13',"维生素A(微克)": '380-1000', "铜(毫克)": '0.4-3', "钾(毫克)": 1100, "磷(毫克)": 350, "钠(毫克)": 800, "硒(微克)": '30-120'
            }

    elif 5 <= age < 6:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 1400, "硫胺素(毫克)":0.9, "钙(毫克)": '600-2000', "蛋白质(克)": '30-70', "核黄素(毫克)": 0.9, "镁(毫克)": 160, "脂肪(克)": '31.11-46.67', "烟酸(毫克)": '7-15',"铁(毫克)": '10-30', "碳水化合物(克)": '175-227.5',
                "维生素C(毫克)": '50-600', "锰(毫克)": '2-3.5', "膳食纤维(克)": '10-15', "维生素E(毫克)": '7-200', "锌(毫克)": '5.5-13', "维生素A(微克)": '390-1000', "铜(毫克)": '0.4-3', "钾(毫克)": 1100, "磷(毫克)": 350, "钠(毫克)": 800, "硒(微克)": '30-120'
            }
        else:
            target_dict = {
                "热量（千卡）": 1400, "硫胺素(毫克)": 0.9, "钙(毫克)": '600-2000', "蛋白质(克)": '30-70', "核黄素(毫克)": 0.8, "镁(毫克)": 160, "脂肪(克)": '31.11-46.67', "烟酸(毫克)": '6-15',"铁(毫克)": '10-30', "碳水化合物(克)": '175-227.5',
                "维生素C(毫克)": '50-600', "锰(毫克)": '2-3.5', "膳食纤维(克)": '10-15', "维生素E(毫克)": '7-200', "锌(毫克)": '5.5-13', "维生素A(微克)": '380-1000', "铜(毫克)": '0.4-3', "钾(毫克)": 1100, "磷(毫克)": 350, "钠(毫克)": 800, "硒(微克)": '30-120'
            }

    elif 6 <= age < 7:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 0.9, "钙(毫克)": '600-2000', "蛋白质(克)": '', "核黄素(毫克)": 0.9, "镁(毫克)": 160, "脂肪(克)": '', "烟酸(毫克)": 7,"铁(毫克)": 10, "碳水化合物(克)": '',
                "维生素C(毫克)": '50-600', "锰(毫克)": 2, "膳食纤维(克)": '10-15', "维生素E(毫克)": '7-200', "锌(毫克)": '5.5-13', "维生素A(微克)": '390-1000', "铜(毫克)": '0.4-3', "钾(毫克)": 1100, "磷(毫克)": 350, "钠(毫克)":800, "硒(微克)": '30-120'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1400
                target_dict["蛋白质(克)"] = '35-70'
                target_dict["碳水化合物(克)"] = '175-227.5'
                target_dict["脂肪(克)"] = '31.11-46.67'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1600
                target_dict["蛋白质(克)"] = '35-80'
                target_dict["碳水化合物(克)"] = '200-260'
                target_dict["脂肪(克)"] = '35.56-53.33'
            else:
                target_dict["热量（千卡）"] = 1800
                target_dict["蛋白质(克)"] = '35-90'
                target_dict["碳水化合物(克)"] = '225-292.5'
                target_dict["脂肪(克)"] = '40-60'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 0.9, "钙(毫克)": '600-2000', "蛋白质(克)": '', "核黄素(毫克)": 0.8, "镁(毫克)": 160, "脂肪(克)": '', "烟酸(毫克)": 6, "铁(毫克)": 10, "碳水化合物(克)": '',
                "维生素C(毫克)": '50-600', "锰(毫克)": 2, "膳食纤维(克)": '10-15', "维生素E(毫克)": '7-200', "锌(毫克)": '5.5-13', "维生素A(微克)": '380-1000', "铜(毫克)": '0.4-3',"钾(毫克)": 1100, "磷(毫克)": 350, "钠(毫克)": 800, "硒(微克)": '30-120'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1300
                target_dict["蛋白质(克)"] = '35-65'
                target_dict["碳水化合物(克)"] = '162.5-211.25'
                target_dict["脂肪(克)"] = '28.89-43.33'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1450
                target_dict["蛋白质(克)"] = '35-72.5'
                target_dict["碳水化合物(克)"] = '181.25-235.625'
                target_dict["脂肪(克)"] = '32.22-48.33'
            else:#
                target_dict["热量（千卡）"] = 1650
                target_dict["蛋白质(克)"] = '35-82.5'
                target_dict["碳水化合物(克)"] = '206.25-268.13'
                target_dict["脂肪(克)"] = '36.67-55'

    elif 7 <= age < 8:#维生素B1又称硫胺素,维生素B2又叫核黄素,胆固醇又称胆甾醇,维生素A（RE）即视黄醇当量没有约束 PI建议摄入量
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1, "镁(毫克)": 200, "脂肪(克)": '', "烟酸(毫克)": '9-19',"铁(毫克)": '12-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '60-800', "锰(毫克)": '2.5-5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '9-300', "锌(毫克)": '7-21', "维生素A(微克)": '430-1300', "铜(毫克)": '0.5-3',"钾(毫克)": 1300, "磷(毫克)": 440, "钠(毫克)": 900, "硒(微克)": '40-150'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1500
                target_dict["蛋白质(克)"] = '40-75'
                target_dict["碳水化合物(克)"] = '187.5-243.75'
                target_dict["脂肪(克)"] = '33.33-50'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1700
                target_dict["蛋白质(克)"] = '40-85'
                target_dict["碳水化合物(克)"] = '212.5-276.25'
                target_dict["脂肪(克)"] = '37.78-56.67'
            else:
                target_dict["热量（千卡）"] = 1900
                target_dict["蛋白质(克)"] = '40-95'
                target_dict["碳水化合物(克)"] = '237.5-308.75'
                target_dict["脂肪(克)"] = '42.22-63.33'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 0.9, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 0.9, "镁(毫克)": 200, "脂肪(克)": '', "烟酸(毫克)": '8-19',"铁(毫克)": '12-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '60-800', "锰(毫克)": '2.5-5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '9-300', "锌(毫克)": '7-21', "维生素A(微克)": '390-1300', "铜(毫克)": '0.5-3', "钾(毫克)": 1300, "磷(毫克)": 440, "钠(毫克)": 900, "硒(微克)": '40-150'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1350
                target_dict["蛋白质(克)"] = '40-67.5'
                target_dict["碳水化合物(克)"] = '168.75-219.375'
                target_dict["脂肪(克)"] = '30-45'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1550
                target_dict["蛋白质(克)"] = '40-77.5'
                target_dict["碳水化合物(克)"] = '193.75-251.88'
                target_dict["脂肪(克)"] = '34.44-51.67'
            else:
                target_dict["热量（千卡）"] = 1750
                target_dict["蛋白质(克)"] = '40-87.5'
                target_dict["碳水化合物(克)"] = '218.75-284.375'
                target_dict["脂肪(克)"] = '38.89-58.33'
    elif 8 <= age < 9:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1, "镁(毫克)": 200, "脂肪(克)": '', "烟酸(毫克)": '9-19',"铁(毫克)": '12-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '60-800', "锰(毫克)": '2.5-5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '9-300', "锌(毫克)": '7-21', "维生素A(微克)": '430-1300', "铜(毫克)": '0.5-3', "钾(毫克)": 1300, "磷(毫克)": 440, "钠(毫克)": 900, "硒(微克)": '40-150'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1600
                target_dict["蛋白质(克)"] = '40-80'
                target_dict["碳水化合物(克)"] = '200-260'
                target_dict["脂肪(克)"] = '35.56-53.33'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1850
                target_dict["蛋白质(克)"] = '40-92.5'
                target_dict["碳水化合物(克)"] = '231.25-300.625'
                target_dict["脂肪(克)"] = '41.1-61.7'
            else:
                target_dict["热量（千卡）"] = 2100
                target_dict["蛋白质(克)"] = '40-105'
                target_dict["碳水化合物(克)"] = '262.5-341.25'
                target_dict["脂肪(克)"] =  '46.67-70'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 0.9, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 0.9, "镁(毫克)": 200, "脂肪(克)": '', "烟酸(毫克)": '8-19', "铁(毫克)": '12-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '60-800', "锰(毫克)": '2.5-5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '9-300', "锌(毫克)": '7-21', "维生素A(微克)": '430-1300', "铜(毫克)": '0.5-3', "钾(毫克)": 1300, "磷(毫克)": 440, "钠(毫克)": 900, "硒(微克)": '40-150'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1450
                target_dict["蛋白质(克)"] = '40-72.5'
                target_dict["碳水化合物(克)"] = '181.25-235.625'
                target_dict["脂肪(克)"] = '32.22-48.33'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1700
                target_dict["蛋白质(克)"] = '40-85'
                target_dict["碳水化合物(克)"] = '212.5-276.25'
                target_dict["脂肪(克)"] = '37.8-56.7'
            else:
                target_dict["热量（千卡）"] = 1900
                target_dict["蛋白质(克)"] = '40-95'
                target_dict["碳水化合物(克)"] = '237.5-308.75'
                target_dict["脂肪(克)"] = '42-63'
    elif 9 <= age < 10:
        #print(gender[0])
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.1, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.1, "镁(毫克)": 250, "脂肪(克)": '', "烟酸(毫克)": '10-23', "铁(毫克)": '16-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '75-1100', "锰(毫克)": '3.5-6.5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '11-450', "锌(毫克)": '7-24', "维生素A(微克)": '560-1800', "铜(毫克)": '0.6-5.0', "钾(毫克)": 1600, "磷(毫克)": 550, "钠(毫克)": 1100, "硒(微克)": '45-200'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1700
                target_dict["蛋白质(克)"] = '45-85'
                target_dict["碳水化合物(克)"] = '212.5-276.25'
                target_dict["脂肪(克)"] = '37.8-56.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1950
                target_dict["蛋白质(克)"] = '45-97.5'
                target_dict["碳水化合物(克)"] = '243.75-316.875'
                target_dict["脂肪(克)"] = '43.33-64.94'
            else:
                target_dict["热量（千卡）"] = 2200
                target_dict["蛋白质(克)"] = '45-110'
                target_dict["碳水化合物(克)"] = '275-357.5'
                target_dict["脂肪(克)"] ='48.89-73.33'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.1, "镁(毫克)": 250, "脂肪(克)": '', "烟酸(毫克)": '10-23',"铁(毫克)": '16-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '75-1100', "锰(毫克)": '3-6.5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '11-450', "锌(毫克)": '7-24', "维生素A(微克)": '540-1800', "铜(毫克)": '0.6-5.0',"钾(毫克)": 1600, "磷(毫克)": 550, "钠(毫克)": 1100, "硒(微克)": '45-200'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1550
                target_dict["蛋白质(克)"] = '45-77.5'
                target_dict["碳水化合物(克)"] = '193.75-251.875'
                target_dict["脂肪(克)"] = '34.44 -51.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1800
                target_dict["蛋白质(克)"] = '45-90'
                target_dict["碳水化合物(克)"] = '225-292.5'
                target_dict["脂肪(克)"] = '40-60'
            else:
                target_dict["热量（千卡）"] = 2000
                target_dict["蛋白质(克)"] = '45-100'
                target_dict["碳水化合物(克)"] = '250-325'
                target_dict["脂肪(克)"] = '44.44-66.7'
    elif 10 <= age < 11:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.1, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.1, "镁(毫克)": 250, "脂肪(克)": '', "烟酸(毫克)": '10-23', "铁(毫克)": '16-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '75-1100', "锰(毫克)": '3.5-6.5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '11-450', "锌(毫克)": 7, "维生素A(微克)": '560-1800', "铜(毫克)": '0.6-5',"钾(毫克)": 1600, "磷(毫克)": 550, "钠(毫克)": 1100, "硒(微克)": '45-200'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1800
                target_dict["蛋白质(克)"] = '50-90'
                target_dict["碳水化合物(克)"] = '225-292.5'
                target_dict["脂肪(克)"] = '40-60'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2050
                target_dict["蛋白质(克)"] = '50-102.5'
                target_dict["碳水化合物(克)"] = '256.25-333.125'
                target_dict["脂肪(克)"] = '45.56-68.33'
            else:
                target_dict["热量（千卡）"] = 2300
                target_dict["蛋白质(克)"] = '50-115'
                target_dict["碳水化合物(克)"] = '287.5-373.75'
                target_dict["脂肪(克)"] = '51.11-77'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1, "镁(毫克)": 250, "脂肪(克)": '', "烟酸(毫克)": '10-23',"铁(毫克)": '16-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '75-1100', "锰(毫克)": '3-6.5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '11-450', "锌(毫克)": 7, "维生素A(微克)": '540-1800', "铜(毫克)": '0.6-5',"钾(毫克)": 1600, "磷(毫克)": 550, "钠(毫克)": 1100, "硒(微克)": '45-200'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1650
                target_dict["蛋白质(克)"] = '50-82.5'
                target_dict["碳水化合物(克)"] = '206.25-268.125'
                target_dict["脂肪(克)"] = '36.67-55'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1900
                target_dict["蛋白质(克)"] = '50-95'
                target_dict["碳水化合物(克)"] = '237.5-308.75'
                target_dict["脂肪(克)"] = '42.22-63'
            else:
                target_dict["热量（千卡）"] = 2100
                target_dict["蛋白质(克)"] = '50-105'
                target_dict["碳水化合物(克)"] = '262.5-341.25'
                target_dict["脂肪(克)"] = '46.67-70'
    elif 11 <= age < 12:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.1, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.1, "镁(毫克)": 250, "脂肪(克)": '', "烟酸(毫克)": '10-23',"铁(毫克)": '16-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '75-1100', "锰(毫克)": '3.5-6.5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '11-450', "锌(毫克)": 7, "维生素A(微克)": '560-1800', "铜(毫克)": '0.6-5',"钾(毫克)": 1600, "磷(毫克)": 550, "钠(毫克)": 1100, "硒(微克)": '45-200'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1900
                target_dict["蛋白质(克)"] = '55-95'
                target_dict["碳水化合物(克)"] = '238-309'
                target_dict["脂肪(克)"] = '42.2-63.3'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2200
                target_dict["蛋白质(克)"] = '55-110'
                target_dict["碳水化合物(克)"] = '275-357.5'
                target_dict["脂肪(克)"] = '48.89-73.33'
            else:
                target_dict["热量（千卡）"] = 2450
                target_dict["蛋白质(克)"] = '55-122.5'
                target_dict["碳水化合物(克)"] = '306.25-398.125'
                target_dict["脂肪(克)"] = '54.44-81.7'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1, "镁(毫克)": 250, "脂肪(克)": '', "烟酸(毫克)": '10-23', "铁(毫克)": '16-35', "碳水化合物(克)": '',
                "维生素C(毫克)": '75-1100', "锰(毫克)": '3-6.5', "膳食纤维(克)": '15-20', "维生素E(毫克)": '11-450', "锌(毫克)": 7, "维生素A(微克)": '540-1800', "铜(毫克)": '0.6-5',"钾(毫克)": 1600, "磷(毫克)": 550, "钠(毫克)": 1100, "硒(微克)": '45-200'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1750
                target_dict["蛋白质(克)"] = '55-88'
                target_dict["碳水化合物(克)"] = '219-284'
                target_dict["脂肪(克)"] = '38.89-58.3'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2000
                target_dict["蛋白质(克)"] = '55-100'
                target_dict["碳水化合物(克)"] = '250-325'
                target_dict["脂肪(克)"] = '44.44-66.67'
            else:
                target_dict["热量（千卡）"] = 2250
                target_dict["蛋白质(克)"] = '55-112.5'
                target_dict["碳水化合物(克)"] = '281.25-365.625'
                target_dict["脂肪(克)"] = '50-75'
    elif 12 <= age < 15:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.4, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.4, "镁(毫克)": 320, "脂肪(克)": '', "烟酸(毫克)": '13-30',"铁(毫克)": '16-40', "碳水化合物(克)": '',
                "维生素C(毫克)": '95-1600', "锰(毫克)": '4.5-9', "膳食纤维(克)": '20-25', "维生素E(毫克)": '13-500', "锌(毫克)": '8.5-32', "维生素A(微克)": '780-2400', "铜(毫克)": '0.7-6',"钾(毫克)": 1800, "磷(毫克)": 700, "钠(毫克)": 1400, "硒(微克)": '60-300'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 2300
                target_dict["蛋白质(克)"] = '70-115'
                target_dict["碳水化合物(克)"] = '287.5-373.75'
                target_dict["脂肪(克)"] = '51.1-76.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2600
                target_dict["蛋白质(克)"] = '70-130'
                target_dict["碳水化合物(克)"] = '325-422.5'
                target_dict["脂肪(克)"] = '57.78-86.7'
            else:
                target_dict["热量（千卡）"] = 2900
                target_dict["蛋白质(克)"] = '70-145'
                target_dict["碳水化合物(克)"] = '362.5-471.25'
                target_dict["脂肪(克)"] = '64.44-96.7'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.2, "钙(毫克)": 1000, "蛋白质(克)": 60, "核黄素(毫克)": 1.2, "镁(毫克)": 320, "脂肪(克)": 0, "烟酸(毫克)": '12-30', "铁(毫克)": '18-40', "碳水化合物(克)": '',
                "维生素C(毫克)": '95-1600', "锰(毫克)": '4-9', "膳食纤维(克)": '20-25', "维生素E(毫克)": '13-500', "锌(毫克)": '7.5-32', "维生素A(微克)": '730-2400', "铜(毫克)": '0.7-6', "钾(毫克)": 1800, "磷(毫克)": 700, "钠(毫克)": 1400, "硒(微克)": '60-300'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1950
                target_dict["蛋白质(克)"] = '60-97.5'
                target_dict["碳水化合物(克)"] = '243.75-316.875'
                target_dict["脂肪(克)"] = '43.33-65'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2200
                target_dict["蛋白质(克)"] = '60-110'
                target_dict["碳水化合物(克)"] = '275-357.5'
                target_dict["脂肪(克)"] = '48.89-73.33'
            else:
                target_dict["热量（千卡）"] = 2450
                target_dict["蛋白质(克)"] = '60-122.5'
                target_dict["碳水化合物(克)"] = '306.25-398.125'
                target_dict["脂肪(克)"] = '54.44-81.67'
    elif 15 <= age < 18:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.6, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.6, "镁(毫克)": 330, "脂肪(克)": '', "烟酸(毫克)": '15-33',"铁(毫克)": '16-40', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-1800', "锰(毫克)": '5-10', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-600', "锌(毫克)": '11.5-37', "维生素A(微克)": '810-2800', "铜(毫克)": '0.8-7',"钾(毫克)": 2000, "磷(毫克)": 720, "钠(毫克)": 1600, "硒(微克)": '60-350'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 2600
                target_dict["蛋白质(克)"] = '75-130'
                target_dict["碳水化合物(克)"] = '325-422.5'
                target_dict["脂肪(克)"] = '57.78-86.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2950
                target_dict["蛋白质(克)"] = '75-147.5'
                target_dict["碳水化合物(克)"] = '368.75-479.375'
                target_dict["脂肪(克)"] = '65.56-98.3'
            else:
                target_dict["热量（千卡）"] = 3300
                target_dict["蛋白质(克)"] = '75-165'
                target_dict["碳水化合物(克)"] = '412.5-536.25'
                target_dict["脂肪(克)"] = '73.33-110'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.3, "钙(毫克)": '1000-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.2, "镁(毫克)": 330, "脂肪(克)": '', "烟酸(毫克)": '12-33', "铁(毫克)": '18-40', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-1800', "锰(毫克)": '4-10', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-600', "锌(毫克)": '8-37', "维生素A(微克)": '670-2800', "铜(毫克)": '0.8-7', "钾(毫克)": 2000, "磷(毫克)": 720, "钠(毫克)": 1600, "硒(微克)": '60-350'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 2100
                target_dict["蛋白质(克)"] = '60-105'
                target_dict["碳水化合物(克)"] = '262.5-341.25'
                target_dict["脂肪(克)"] = '46.67-70'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2350
                target_dict["蛋白质(克)"] = '60-117.5'
                target_dict["碳水化合物(克)"] = '293.75-381.875'
                target_dict["脂肪(克)"] = '52.22-78.3'
            else:
                target_dict["热量（千卡）"] = 2650
                target_dict["蛋白质(克)"] = '60-132.5'
                target_dict["碳水化合物(克)"] = '331.25-430.625'
                target_dict["脂肪(克)"] = '58.89-88'
    elif 18 <= age < 30:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.4, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.4, "镁(毫克)": 330, "脂肪(克)": '', "烟酸(毫克)": '15-35', "铁(毫克)": '12-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4.5-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '12-40', "维生素A(微克)": '770-3000', "铜(毫克)": '0.8-8',"钾(毫克)": 2000, "磷(毫克)": '720-3500', "钠(毫克)": 1500, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 2150
                target_dict["蛋白质(克)"] = '65-107.5'
                target_dict["碳水化合物(克)"] = '268.75-349.375'
                target_dict["脂肪(克)"] = '47.8-71.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2550
                target_dict["蛋白质(克)"] = '65-127.5'
                target_dict["碳水化合物(克)"] = '319-414'
                target_dict["脂肪(克)"] = '56.67-85'
            else:
                target_dict["热量（千卡）"] = 3000
                target_dict["蛋白质(克)"] = '65-150'
                target_dict["碳水化合物(克)"] = '375-487.5'
                target_dict["脂肪(克)"] = '66.67-100'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.2, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.2, "镁(毫克)": 330, "脂肪(克)": '', "烟酸(毫克)": '12-35', "铁(毫克)": '18-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '8.5-40', "维生素A(微克)": '660-3000', "铜(毫克)": '0.8-8', "钾(毫克)": 2000, "磷(毫克)": '720-3500', "钠(毫克)": 1500, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1700
                target_dict["蛋白质(克)"] = '55-85'
                target_dict["碳水化合物(克)"] = '212.5-276.25'
                target_dict["脂肪(克)"] = '37.78-56.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2100
                target_dict["蛋白质(克)"] = '55-105'
                target_dict["碳水化合物(克)"] = '262.5-341.25'
                target_dict["脂肪(克)"] = '46.67-70'
            else:
                target_dict["热量（千卡）"] = 2450
                target_dict["蛋白质(克)"] = '55-122.5'
                target_dict["碳水化合物(克)"] = '306.25-398.125'
                target_dict["脂肪(克)"] = '54.44-81.7'
    elif 30 <= age < 50:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.4, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.4, "镁(毫克)": 320, "脂肪(克)": '', "烟酸(毫克)": '15-35',"铁(毫克)": '12-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4.5-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '12-40', "维生素A(微克)": '770-3000', "铜(毫克)": '0.8-8', "钾(毫克)": 2000, "磷(毫克)": '710-3500', "钠(毫克)": 1500, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 2050
                target_dict["蛋白质(克)"] = '65-102.5'
                target_dict["碳水化合物(克)"] = '256.25-333.125'
                target_dict["脂肪(克)"] = '45.56-68.3'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2500
                target_dict["蛋白质(克)"] = '65-125'
                target_dict["碳水化合物(克)"] = '312.5-406.25'
                target_dict["脂肪(克)"] = '55.56-83.3'
            else:
                target_dict["热量（千卡）"] = 2950
                target_dict["蛋白质(克)"] = '65-147.5'
                target_dict["碳水化合物(克)"] = '368.75-479.375'
                target_dict["脂肪(克)"] = '65.56-98.3'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.2, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.2, "镁(毫克)": 320, "脂肪(克)": '', "烟酸(毫克)": '12-35',"铁(毫克)": '18-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)":'8.5-40', "维生素A(微克)": '660-3000', "铜(毫克)": '0.8-8', "钾(毫克)": 2000, "磷(毫克)": '710-3500', "钠(毫克)": 1500, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1700
                target_dict["蛋白质(克)"] = '55-85'
                target_dict["碳水化合物(克)"] = '368.75-276'
                target_dict["脂肪(克)"] = '37.8-56.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2050
                target_dict["蛋白质(克)"] = '55-102.5'
                target_dict["碳水化合物(克)"] = '368.75-333.125'
                target_dict["脂肪(克)"] = '45.56-68.3'
            else:
                target_dict["热量（千卡）"] = 2400
                target_dict["蛋白质(克)"] = '55-120'
                target_dict["碳水化合物(克)"] = '368.75-390'
                target_dict["脂肪(克)"] = '53.33-80'
    elif 50 <= age < 65:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.4, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.4, "镁(毫克)": 320, "脂肪(克)": '', "烟酸(毫克)": 15,"铁(毫克)": '12-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4.5-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '12-40', "维生素A(微克)": '750-3000', "铜(毫克)": '0.8-8', "钾(毫克)": 2000, "磷(毫克)": '710-3500', "钠(毫克)": 1500, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1950
                target_dict["蛋白质(克)"] = '65-97.5'
                target_dict["碳水化合物(克)"] = '243.75-319.375'
                target_dict["脂肪(克)"] = '43.33-65'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2400
                target_dict["蛋白质(克)"] = '65-120'
                target_dict["碳水化合物(克)"] = '300-390'
                target_dict["脂肪(克)"] = '53.33-80'
            else:
                target_dict["热量（千卡）"] = 2800
                target_dict["蛋白质(克)"] = '65-140'
                target_dict["碳水化合物(克)"] = '350-455'
                target_dict["脂肪(克)"] = '62.22-93.3'
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.2, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.2, "镁(毫克)": 320, "脂肪(克)": '', "烟酸(毫克)": '12-35', "铁(毫克)": '10-42', "碳水化合物(克)":'',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '8.5-40', "维生素A(微克)": '660-3000', "铜(毫克)": '0.8-8', "钾(毫克)": 2000, "磷(毫克)": '710-3500', "钠(毫克)": 1500, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1600
                target_dict["蛋白质(克)"] = '55-80'
                target_dict["碳水化合物(克)"] = '200-260'
                target_dict["脂肪(克)"] = '35.56-53.3'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1950
                target_dict["蛋白质(克)"] = '55-97.5'
                target_dict["碳水化合物(克)"] = '243.75-316.88'
                target_dict["脂肪(克)"] = '43.33-65'
            else:
                target_dict["热量（千卡）"] = 2300
                target_dict["蛋白质(克)"] = '55-115'
                target_dict["碳水化合物(克)"] = '287.5-373.75'
                target_dict["脂肪(克)"] = '51.11-76.7'
    elif 65 <= age < 75:
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.4, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.4, "镁(毫克)": 310, "脂肪(克)": '', "烟酸(毫克)": '15-35',"铁(毫克)": '12-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4.5-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '12-40', "维生素A(微克)": '730-3000', "铜(毫克)": '0.8-8',"钾(毫克)": 2000, "磷(毫克)": '680-3000', "钠(毫克)": 1400, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1900
                target_dict["蛋白质(克)"] = '71.25-95'
                target_dict["碳水化合物(克)"] = '237.5-308.75'
                target_dict["脂肪(克)"] = '42.22-63.3'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2300
                target_dict["蛋白质(克)"] = '72-115'
                target_dict["碳水化合物(克)"] = '287.5-373.75'
                target_dict["脂肪(克)"] = '51.11-76.7'
            else:
                print('未设定')
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.2, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.2, "镁(毫克)": 310, "脂肪(克)": '', "烟酸(毫克)": '12-35',"铁(毫克)": '10-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '8.5-40', "维生素A(微克)": '640-3000', "铜(毫克)": '0.8-8',"钾(毫克)": 2000, "磷(毫克)": '680-3000', "钠(毫克)": 1400, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1550
                target_dict["蛋白质(克)"] = '62-77.5'
                target_dict["碳水化合物(克)"] = '193.75-251.875'
                target_dict["脂肪(克)"] = '34.44-51.7'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1850
                target_dict["蛋白质(克)"] = '62-92.5'
                target_dict["碳水化合物(克)"] = '231.25-300.625'
                target_dict["脂肪(克)"] = '41.11-61.7'
            else:
                print('未设定')
    else:#75-
        if gender[0] == "男":
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.4, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.4, "镁(毫克)": 300, "脂肪(克)": '', "烟酸(毫克)": '15-35', "铁(毫克)": '12-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4.5-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '12-40', "维生素A(微克)": '710-3000', "铜(毫克)": '0.7-8',"钾(毫克)": 2000, "磷(毫克)": '680-3000', "钠(毫克)": 1400, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1800
                target_dict["蛋白质(克)"] = '72-90'
                target_dict["碳水化合物(克)"] = '225-292.5'
                target_dict["脂肪(克)"] = '40-60'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 2200
                target_dict["蛋白质(克)"] = '72-110'
                target_dict["碳水化合物(克)"] = '275-357.5'
                target_dict["脂肪(克)"] = '48.89-73.3'
            else:
                print('未设定')
        else:
            target_dict = {
                "热量（千卡）": 0, "硫胺素(毫克)": 1.2, "钙(毫克)": '800-2000', "蛋白质(克)": '', "核黄素(毫克)": 1.2, "镁(毫克)": 300, "脂肪(克)": '', "烟酸(毫克)": '12-35', "铁(毫克)": '10-42', "碳水化合物(克)": '',
                "维生素C(毫克)": '100-2000', "锰(毫克)": '4-11', "膳食纤维(克)": '25-30', "维生素E(毫克)": '14-700', "锌(毫克)": '8.5-40', "维生素A(微克)": '600-3000', "铜(毫克)": '0.7-8',"钾(毫克)": 2000, "磷(毫克)": '680-3000', "钠(毫克)": 1400, "硒(微克)": '60-400'
            }
            if pal[0] == "低":
                target_dict["热量（千卡）"] = 1500
                target_dict["蛋白质(克)"] = '62-75'
                target_dict["碳水化合物(克)"] = '187.5-243.75'
                target_dict["脂肪(克)"] = '33.33-50'
            elif pal[0] == "中":
                target_dict["热量（千卡）"] = 1750
                target_dict["蛋白质(克)"] = '62-87.5'
                target_dict["碳水化合物(克)"] = '218.75-284.375'
                target_dict["脂肪(克)"] = '38.89-58.3'
            else:
                print('未设定')

    parsed_values = {k: parse_range(v) for k, v in target_dict.items()}
    # 移除指定键值对
    keys_to_remove = ['热量（千卡）', '碳水化合物(克)']
    for key in keys_to_remove:
        parsed_values.pop(key, None)  # 使用 pop 并设置默认值，避免键不存在时报错
    # values = np.array([v for sublist in parsed_values.values() for v in sublist])
    # print(values)
    # values = np.array([value/3 for value in target_dict .values()])

    return parsed_values

def parse_range(value):
    # 检查是否是范围字符串
    if isinstance(value, str) and '-' in value:
        # 分割字符串为上下限
        low, high = value.split('-')
        # 将字符串转换为浮点数并除以3
        return float(low) / 3, float(high) / 3
    else:
        # 如果不是范围字符串，直接返回原值除以3
        return value / 3
# Load step10testData.csv file with custom column names
# file_path = './save/step10testData.csv'
# column_names = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']  # Customize these as needed

file_path =r"D:\code\MOBO\zj\analysis_recipes\file\output_wenxin\sampled_output.csv" #r'D:\code\MOBO\zj\analysis_recipes\file\output_wenxin\sampled_output.csv'
column_names = ['A', 'B','C', 'D']
data = pd.read_csv(file_path, names=column_names,skiprows=1)  # skiprows=1 to skip the header row if it exists

# Initialize a list to store results

#age_ranges = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10),(10, 11), (11, 12),(12, 15), (15, 18), (18, 30), (30, 50), (50, 65), (65, 75), (75, 100)]
age_ranges = [(18, 30)]
# gender =['男', '女']
# pal =['低', '中', '高']
for age_range in age_ranges:
    age=(age_range[0] + age_range[1]) / 2
    gender = ['男']  # ['男', '女']
    pal =['低']# ['低', '中', '高'] 从6岁开始分低中高
    results = []
    suitable_combinations = []
    for index, row in data.iterrows():
        # input_str_c7 = str(row['F']).strip()
        # input_str_c8 = str(row['G']).strip()
        #
        # # Combine input strings
        # combined_input_str = input_str_c7 + "," + input_str_c8
        combined_input_str =str(row['B']).strip()
        combined_input_str=converter.convert(combined_input_str)
        #combined_input_str = re.sub(r' ', '', combined_input_str)
        #print(combined_input_str)

        # if "盐" not in combined_input_str:
        #     # 如果没有 "盐" 和 "油"，则追加
        #     combined_input_str += ",盐: 1克"
        #
        # # 列出常见的食用油类
        # edible_oils = ["炒菜油","底油", "植物油", "花生油", "菜籽油", "玉米油", "菜油", "橄榄油", "食用油", "豆油", "香油", "芝麻油","麻油", "色拉油","葵花籽油","瓜子油","黄油","鸡油","鸭油","板油","猪油","动物油","牛油","羊油","鹅油","明油","滚油","热油","冷油","茶油"]
        # # 检查是否已经有常见的食用油
        # contains_edible_oil = any(edible_oil in combined_input_str for edible_oil in edible_oils)
        # # 如果只包含非食用油且没有常见食用油，则追加食用油
        # if not contains_edible_oil:
        #     combined_input_str += ",食用油: 1克"

        # Load nutrition data
        nutrition_df = load_nutrition_data()#每一行代表一种食物
        print(combined_input_str)
        flag=0
        num=2#gpt回答num-1次
        suitable_combinations = []
        new_recipe=combined_input_str#不用chatgpt修改，直接符合的保存
        while flag<num:
            try:
                ingredients_list = new_recipe.split(',')
            except:
                break
            if len(ingredients_list)<2:
                break

            # 初始化结果列表
            ingredients = []

            # 遍历每一个食材信息
            for item in ingredients_list:
                # 去除多余空格，并按冒号分割
                try:
                    name, amount = re.split(r':|：|: |： ', item.strip())
                    # name, amount = item.strip().split(':')
                    # 去除单位并转换为整数
                    amount = float(amount.replace('克.', '').replace('克', '').replace('g', '').strip())
                except:
                    continue
                # 添加为元组到结果列表
                if "水" not in name and "冰块" not in name and "白开" not in name:
                    ingredients.append((name.strip(), amount))
            print(ingredients)
            if len(ingredients)<2:
                break

            # Calculate total nutrients
            nutrient_sums,matched_ings,new_recipe = calculate_nutrients(ingredients, nutrition_df)
            target_keys = ['硫胺素(毫克)', '钙(毫克)', '蛋白质(克)', '核黄素(毫克)', '镁(毫克)', '脂肪(克)', '烟酸(毫克)',
                           '铁(毫克)', '维生素C(毫克)', '锰(毫克)', '膳食纤维(克)', '维生素E(毫克)', '锌(毫克)',
                           '维生素A(微克)', '铜(毫克)', '钾(毫克)', '磷(毫克)', '钠(毫克)', '硒(微克)']
            nutrient_sums2 = pd.DataFrame([nutrient_sums], columns=target_keys)
            # Iterate over all possible age ranges, genders, and activity levels
            # # age_ranges = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 15),
            # #               (15, 18), (18, 30), (30, 50), (50, 65), (65, 75), (75, 100)]
            # age_range = [(18, 30)]
            # gender =['男'] #['男', '女']
            # pal =['中']# ['低', '中', '高']
            target_nutrients = obtain_target((age_range[0] + age_range[1]) / 2, gender, pal)
            target_nutrients2 = pd.DataFrame([target_nutrients], columns=target_keys)
            if flag!=num-1:
                # 将索引重置为默认整数索引，并将之前的索引列变回普通列
                nutrition_df.reset_index(inplace=True)
                cols = nutrition_df.columns.tolist()
                cols.insert(1, cols.pop(0))  # 将第一列插入到第二列位置
                nutrition_df = nutrition_df[cols]
                new_recipe= adjust_recipe(new_recipe, target_nutrients2, matched_ings,nutrient_sums2,nutrition_df)
                print('新食谱是:'+new_recipe)
                flag = flag + 1
            else:
                suitability,yes,no = check_suitability(nutrient_sums, target_nutrients)
                if suitability:
                    suitable_combinations.append((age_range, gender[0], pal[0],yes,no))
                    break

        # Append the results for this row to the results list
        if suitable_combinations != []:
            results.append({
                'index': index,
                'ingredients': new_recipe,
                'suitable_combinations': suitable_combinations
            })#

    # # Output results
    # for result in results:
    #     print(f"行 {result['index']} 的总的营养素含量：{result['nutrient_sums']}")
    #     print(f"适用的年龄段、性别和劳动强度组合：{result['suitable_combinations']}")
    # 将结果保存到 CSV 文件
    file_name='D:\code\MOBO\zj\\analysis_recipes\\no_add_newingredient\gpt'+str(age_range)+'_男_低_results_o3_mini.csv'#D:\code\MOBO\zj\analysis_recipes\no_add_newingredient\gpt
    save_results_to_csv(results, file_name)