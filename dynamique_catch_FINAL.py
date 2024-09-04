import requests
import time
import json
import datetime
import pandas as pd
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm.asyncio import tqdm_asyncio
from tqdm import tqdm

headers = {'Content-Type': 'application/json'}
eslworkingLists = [
    '10.128.92.236:9000',
]  # 示例IP地址列表

def int_to_bin(s):
    s = hex(s)[2:]
    bin1 = ''
    for i in range(4):
        try:
            out = int(s[i * 2:i * 2 + 2], 16)
            out = format(out, "08b")
            bin1 += out
        except:
            continue
    return bin1

def product_detail(product):
    data = int_to_bin(product)
    c = data[5:7]
    cc = {'00': 'stellarPro', '01': 'TI-CC2640', '10': '泰凌微8258', '11': 'nebular'}
    return cc[c]

async def fetch_store_data(session, eslworking, store, index, semaphore):
    async with semaphore:
        try:
            url = f'http://{eslworking}/api3/{store}/esls/page/{index}'
            async with session.get(url) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

async def fetch_esl_data(session, eslworking, esl_id, semaphore):
    async with semaphore:
        try:
            url = f'http://{eslworking}/api3/esls/{esl_id}'
            async with session.get(url) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

async def process_store(session, eslworking, store, max_records_per_store, yesterday_str, semaphore, pbar):
    index = 1
    store_results = []

    while True:
        store_data = await fetch_store_data(session, eslworking, store['user'], index, semaphore)
        if not store_data or 'data' not in store_data or not store_data['data']['esls'] or len(store_results) >= max_records_per_store:
            break
        esls = store_data['data']['esls']
        for esl in esls:
            if len(store_results) >= max_records_per_store:
                break
            try:
                esl_data = await fetch_esl_data(session, eslworking, esl['esl_id'], semaphore)
                if esl_data is None or 'data' not in esl_data:
                    continue
                value = esl_data['data']
                dt = int(value['last_hb_time'])
                df = int(value['create_time'])
                battery = int(value['battery'])

                dt_str = datetime.datetime.fromtimestamp(dt / 1000).strftime("%Y-%m-%d %H:%M:%S")
                df_str = datetime.datetime.fromtimestamp(df / 1000).strftime("%Y-%m-%d %H:%M:%S")

                if dt_str >= yesterday_str:
                    product_id = value['product_id']
                    if product_id != 0 and product_id is not None:
                        product_id = product_detail(product_id)

                    time_diff_days = (dt - df) // (1000 * 60 * 60 * 24)
                    frequency = int(value['refresh_times']) / time_diff_days if time_diff_days > 0 else 0

                    res = {
                        "价签ID": str(value['esl_id']),
                        "门店": str(value['user']),
                        "创建时间": df_str,
                        "电量": str(battery),
                        "最后心跳时间": dt_str,
                        "尺寸": str(value['screen_size']),
                        "描述": str(value['description']),
                        "刷屏次数": str(value['refresh_times']),
                        "闪灯时长": str(value['led_times']),
                        "firmware": str(value['firmware']),
                        "rom": str(value['rom']),
                        "extesl_id": str(value['extesl_id']),
                        "product_id": str(product_id),
                        "set_wor": str(value['set_wor']),
                        "frequency": frequency
                    }
                    store_results.append(res)
                    pbar.update(1)  # 更新进度条
            except Exception as e:
                print(f"Error processing ESL ID {esl['esl_id']} on {eslworking}: {e}")
        index += 1
        await asyncio.sleep(1)
    return store_results

async def adjust_semaphore(semaphore, avg_response_time, target_response_time):
    """
    动态调整信号量并发数量
    :param semaphore: 当前信号量对象
    :param avg_response_time: 当前的平均响应时间
    :param target_response_time: 目标响应时间
    """
    if avg_response_time > target_response_time:
        # 如果响应时间过长，减少并发
        new_limit = max(1, semaphore._value - 1)
        semaphore = asyncio.Semaphore(new_limit)
        print(f"Reducing concurrency to {new_limit}")
    elif avg_response_time < target_response_time and semaphore._value < 20:  # 假设最大并发数是20
        # 如果响应时间较短，增加并发
        new_limit = semaphore._value + 1
        semaphore = asyncio.Semaphore(new_limit)
        print(f"Increasing concurrency to {new_limit}")
    return semaphore

async def code(eslworking, max_records_per_store, semaphore):
    yesterday = datetime.datetime.now() - datetime.timedelta(days=7)
    yesterday_str = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    response_times = []

    async with aiohttp.ClientSession() as session:
        eslUrl = f'http://{eslworking}/api3/users'
        async with session.get(eslUrl) as req:
            stores = await req.json()

        total_esls = sum(len(store['esls']) for store in stores['data'] if 'esls' in store)
        with tqdm(total=total_esls, desc=f"Processing {eslworking}", unit="esl") as pbar:
            tasks = []
            for store in stores['data'] if store['user'] != 'default':
                start_time = time.time()
                task = process_store(session, eslworking, store, max_records_per_store, yesterday_str, semaphore, pbar)
                tasks.append(task)
                response_times.append(time.time() - start_time)

            results = await asyncio.gather(*tasks)

            # 动态调整并发
            if len(response_times) > 10:
                avg_response_time = sum(response_times) / len(response_times)
                semaphore = await adjust_semaphore(semaphore, avg_response_time, 2)  # 目标响应时间为2秒
                response_times = []  # 重置计时列表

        return [item for sublist in results for item in sublist]

def write_to_csv(file_index, list_resultat):
    if list_resultat:
        df = pd.DataFrame(list_resultat)
        df = df.sort_values(by='frequency', ascending=True)
        filename = f'esl_id_part_{file_index + 1}.csv'
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"Data written to {filename}")
    else:
        print(f"No results to write to esl_id_part_{file_index + 1}.csv")

def main():
    max_stores_per_file = 1
    max_records_per_store = 50000
    max_concurrent_requests = 4  # 初始最大并发请求数
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    total_files = (len(eslworkingLists) + max_stores_per_file - 1) // max_stores_per_file

    for file_index in range(total_files):
        start_index = file_index * max_stores_per_file
        end_index = min((file_index + 1) * max_stores_per_file, len(eslworkingLists))
        list_resultat = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            futures = [
                executor.submit(loop.run_until_complete, code(eslworking, max_records_per_store, semaphore))
                for eslworking in eslworkingLists[start_index:end_index]
            ]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    list_resultat.extend(result)
                except Exception as e:
                    print(f"Thread raised an exception: {e}")

        write_to_csv(file_index, list_resultat)

if __name__ == '__main__':
    main()
