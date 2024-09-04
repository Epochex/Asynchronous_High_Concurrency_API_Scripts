import aiohttp
import asyncio
import time
import json
import csv
import datetime
import os
from collections import defaultdict

headers = {'Content-Type': 'application/json'}  
eslworkingLists = [
                '10.103.200.236:9000',
                    ]

def int_to_bin(s):
    s = hex(s)[2:]
    bin1 = ''
    for i in (0, 1, 2, 3):
        try:
            out = int(s[i * 2:i * 2 + 2], 16)
            out = format(out, '08b')
            bin1 = bin1 + out
        except:
            continue
    return bin1

def product_detail(product):
    data = int_to_bin(product)
    c = data[5:7]
    cc = {'00': 'stellarPro', '01': 'TI-CC2640', '10': '泰凌微8258', '11': 'nebular'}
    return cc[c]

async def fetch_esl_data(session, eslworking, store_user, index):
    url = f'http://{eslworking}/api3/{store_user}/esls/page/{index}'
    async with session.get(url) as response:
        return await response.json()

async def fetch_esl_detail(session, eslworking, esl_id):
    url = f'http://{eslworking}/api3/esls/{esl_id}'
    async with session.get(url) as response:
        return await response.json()

def calculate_days_difference(last_hb_time, create_time):
    last_hb_date = datetime.datetime.fromtimestamp(last_hb_time / 1000).date()
    create_date = datetime.datetime.fromtimestamp(create_time / 1000).date()
    return (last_hb_date - create_date).days

async def process_store(session, eslworking, store, esl_data):
    for index in range(1, 1000):
        if store['user'] == 'default':
            break
        value = await fetch_esl_data(session, eslworking, store['user'], index)
        if value['data']['total_page'] < index:
            break
        esls = value['data']['esls']
        for eslid in esls:
            try:
                value = await fetch_esl_detail(session, eslworking, eslid['esl_id'])
                resolution_time = value['data']['last_hb_time']
                resolution_time2 = value['data']['create_time']
                dt = int(resolution_time)
                df = int(resolution_time2)
                if eslid['esl_id'] in esl_data:
                    if dt <= esl_data[eslid['esl_id']]['last_hb_time']:
                        continue
                esl_data[eslid['esl_id']] = {
                    'last_hb_time': dt,
                    'create_time': df,
                    'battery': int(value['data']['battery']),
                    'screen_size': value['data']['screen_size'],
                    'description': value['data']['description'],
                    'user': value['data']['user'],
                    'refresh_times': value['data']['refresh_times'],
                    'led_times': value['data']['led_times'],
                    'firmware': value['data']['firmware'],
                    'set_wor': value['data']['set_wor'],
                    'rom': value['data']['rom'],
                    'extesl_id': value['data']['extesl_id'],
                    'product_id': value['data']['product_id'],
                    'temperature': value['data']['temperature']
                }
            except Exception as e:
                print(f"Error processing esl_id {eslid['esl_id']}: {e}")
                continue

async def process_batch(eslworking_batch, batch_index):
    esl_data = defaultdict(dict)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for eslworking in eslworking_batch:
            eslUrl = f'http://{eslworking}/api3/users'
            async with session.get(eslUrl) as req:
                stores = await req.json()
                for store in stores['data']:
                    tasks.append(process_store(session, eslworking, store, esl_data))
        
        await asyncio.gather(*tasks)
    
    directory = './catch_data_csv'
    os.makedirs(directory, exist_ok=True)
    
    filename = f'{directory}/esl_id-all_batch_{batch_index}_{time.strftime("%Y%m%d", time.localtime())}.csv'
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(["价签ID", "门店", "创建时间", "电量", "最后心跳时间", "尺寸", "描述", "刷新率", "闪灯时长", "firmware", "rom", "extesl_id", "product_id", "set_wor"])
        
        for esl_id, data in esl_data.items():
            days_difference = calculate_days_difference(data['last_hb_time'], data['create_time'])
            if days_difference == 0:
                continue
            refresh_rate = data['refresh_times'] / days_difference
            last_hb_time_str = datetime.datetime.fromtimestamp(data['last_hb_time'] / 1000).strftime("%Y-%m-%d")
            create_time_str = datetime.datetime.fromtimestamp(data['create_time'] / 1000).strftime("%Y-%m-%d")
            product_id = product_detail(data['product_id']) if data['product_id'] != 0 and data['product_id'] is not None else data['product_id']
            csv_writer.writerow([esl_id, data['user'], create_time_str, data['battery'], last_hb_time_str,
                                 data['screen_size'], data['description'], refresh_rate, data['led_times'],
                                 data['firmware'], data['rom'], data['extesl_id'], product_id, data['temperature'],
                                 data['set_wor']])
            print(esl_id, last_hb_time_str, create_time_str, data['battery'], data['user'], data['screen_size'], data['description'])

async def main():
    batch_size = 20
    for i in range(0, len(eslworkingLists), batch_size):
        eslworking_batch = eslworkingLists[i:i + batch_size]
        await process_batch(eslworking_batch, i // batch_size + 1)

if __name__ == '__main__':
    asyncio.run(main())
