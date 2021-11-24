# -*- coding: UTF-8 -*-
import os
import shutil
import argparse
import time
import pandas as pd
from numpy import random
import csv
import argparse
import time
import requests
import json
import threading
from queue import Queue
import traceback
from lxml import etree
from retrying import retry
import httpx


class MyThread(threading.Thread):
    def __init__(self, target, args=()):
        super(MyThread, self).__init__()
        self.func = target
        self.args = args
        self.result = ''

    def run(self):
        self.result = self.func(*self.args)

    def get_result(self):
        try:
            # 如果子线程不使用join方法，此处可能会报没有self.result的错误
            return self.result
        except Exception:
            return None


def retry_if_io_error(exception):
    return isinstance(exception, IOError)


class DownloadAPK:
    def __init__(self, save_dir=None, thread_num=3, fpath_pre_urls='', log_download=''):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0',
            'Host': 'www.apkmonk.com',
        }
        self.apkmonk = 'https://www.apkmonk.com/app'
        self.thread_num = thread_num
        self.save_dir = save_dir
        self.filepath_pre_urls = fpath_pre_urls
        self.log_download = log_download

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)


    @retry(retry_on_exception=retry_if_io_error, stop_max_attempt_number=5, wait_random_min=2000, wait_random_max=5000)
    def extract_pkg_and_download(self, pkg):
        '''
        Extract the real download url behind the website Apkmonk for a given app pkg.
        '''
        # 第一层url
        # print('**1')
        url_jump = self.apkmonk + '/' + pkg + '/'
        print("第一层url获取成功: ",url_jump)
        client = httpx.Client(http2=True, verify=False)
        response = client.get(url_jump, headers=self.headers)

        if '<h1>Not Found</h1>' in response.text:
            print(f'{pkg} ---> not found!')
            os.system(f"echo {pkg},{'not found'},{''},{''},{''} >> {self.filepath_pre_urls}")
            return False, []

        status_code = response.status_code
        if status_code != requests.codes.ok:
            print(f"Request Get Error!!  code={status_code}")
            os.system(f"echo {pkg},{'request_faild_1'},{''},{''},{''} >> {self.filepath_pre_urls}")
            return False, []

        html = etree.HTML(response.text)

        # selector = html.xpath('/html/body/main/div/div/div[1]/div[*]/div[2]/table/tbody/tr[*]/td[*]/a')
        selector = html.xpath('//table/tbody/tr[*]/td[*]/a')
        if selector == []:
            print(f"echo {pkg},{'xpath_empty'}!!")
            os.system(f"echo {pkg},{'xpath_empty'},{''},{''},{''} >> {self.filepath_pre_urls}")
            return False, []

        flag_all_succ = True
        for item in selector:
            # 第二层url
            # print('**2')
            _link = item.attrib.get('href','').strip('/')
            _title = item.attrib.get('title','').strip()
            if _link == '' or _title == '' or (not _title.startswith('download')):
                continue
            try:
                _text = item.text.strip()
                version = _text
                param_apk = _link.split('/')[-1]   # not a link
                param_pkg = _link.split('/')[-2]
            except:
                continue

            # 获取已经下载成功的apk
            processed_apk_list = os.listdir(self.save_dir)

            # 过滤掉已经成功下载的apk
            if param_apk in processed_apk_list:
                print(f'already downloaded apk:  {param_apk}')
                continue

            # 第三层url
            # print('**3')
            request_link = f'https://www.apkmonk.com/down_file/?pkg={param_pkg}&key={param_apk}'
            response = client.get(request_link, headers=self.headers)
            status_code = response.status_code
            if status_code != requests.codes.ok:
                flag_all_succ = False
                continue

            # 获取download url
            response_dict = json.loads(response.content)
            previous_download_url = response_dict.get('url')
            print(param_pkg, param_apk, previous_download_url)
            print("获取download url成功: ",previous_download_url)

            # 下载
            try:
                save_path = os.path.join(self.save_dir, param_apk)
                status = self.download_simple(previous_download_url, save_path)
                if status == 'OK':
                    print(f'{pkg},download_succ,{param_apk},{version}')
                    os.system(f"echo {pkg},{'download_succ'},{param_apk},{version} >> {self.log_download}")
                else:
                    print('**************', status)
                    print(f'{pkg},download_error,{param_apk},{version}')
                    os.system(f"echo {pkg},{'download_error'},{version} >> {self.log_download}")
                    flag_all_succ = False
            except:
                traceback.print_exc()
                print('**************')
                print(f'{pkg},error,{param_apk},{version}')
                os.system(f"echo {pkg},{'download_error'},{param_apk} >> {self.log_download}")
                flag_all_succ = False
                continue

        # 当前pkg的所有版本都下载完
        if flag_all_succ == True:
            os.system(f"echo {pkg},{'all_finished'},{''},{''},{''} >> {self.filepath_pre_urls}")

        return True, []


    def download_multithread(self, queue, mutex):
        # 获取总数目
        mutex.acquire()
        total_size = queue.qsize()
        mutex.release()

        while True:
            mutex.acquire()  # 多线程加锁
            qsize = queue.qsize()  # 当前队列中剩余信息数目
            if qsize != 0:
                pkg = queue.get()
                mutex.release()  # 多线程解锁
                try:
                    print(f'{total_size - qsize}/{total_size}     {pkg}......')
                    # 获取url
                    flag_ext_url, _ = self.extract_pkg_and_download(pkg)

                except Exception as e:
                    traceback.print_exc()
            else:
                mutex.release()
                break


    @retry(retry_on_exception=retry_if_io_error, stop_max_attempt_number=5, wait_random_min=2000, wait_random_max=5000)
    def download_simple(self, url, save_path):
        '''
        不使用stream方式下载，会临时保存在内存中,下载完成整体写入磁盘.
        '''
        status = 'OK'
        client = httpx.Client(http2=True, verify=False)
        print("下载：",url)
        response = client.get(url, headers=self.headers)

        print('##',response.status_code)

        if response.status_code == requests.codes.ok:
            print("下载成功：",url)
            with open(save_path, 'wb') as f:
                f.write(response.content)
        else:
            status = 'Download_Failed'
        return status


    def download_previous_apks(self, pkg_lst):
        mutex = threading.Lock()
        q = Queue()  # 创建多线程共享队列
        for pkg in pkg_lst:
            q.put(pkg)

        threads = []
        for i in range(self.thread_num):
            threads.append(MyThread(target=self.download_multithread, args=(q, mutex)))
        for i in range(self.thread_num):
            #time.sleep(0.1)
            threads[i].start()
        for i in range(self.thread_num):
            time.sleep(0.1)
            threads[i].join()
        print('Task Finished!')




def filter_pkgs(all_pkg_lst, filter_log_path):
    processed_pkg = []
    if os.path.exists(filter_log_path):
        with open(filter_log_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    tmp_lst = line.split(',')
                    pkg = tmp_lst[0]
                    status = tmp_lst[1]
                    if status == 'all_finished':
                        processed_pkg.append(pkg)
                except:
                    pass

    new_pkg_lst = []
    for pkg in all_pkg_lst:
        if pkg not in processed_pkg:
            new_pkg_lst.append(pkg)
    return new_pkg_lst


# 读取csv中所有的pkg名称
def get_pkgs(file):
    meta = pd.read_csv(file, index_col='PKG')
    pkg_lst = []
    for pkg in meta.index:
        if pkg not in pkg_lst:
            pkg_lst.append(pkg)
    return pkg_lst




if __name__ == '__main__':
    threads = 2
    root_dir = os.path.dirname(os.path.abspath(__file__))
    input_all_ai_apk_file = f'{root_dir}/meta-apk/apks.csv'
    output_dir = f'{root_dir}/apks'
    fpath_apk_urls = f'{root_dir}/logFiles/pkg_download_logs.txt'
    fpath_download_log = f'{root_dir}/logFiles/apk_download_log.txt'

    # 下载pkg_list中pkg对应的previous pkgs
    downloader = DownloadAPK(save_dir=output_dir, thread_num=threads, fpath_pre_urls=fpath_apk_urls,
                             log_download=fpath_download_log)

    # ********************************************** 第一步 获取url_list*************************************************
    # 1. 获取所有的pkg_list
    all_pkg_list1 = get_pkgs(input_all_ai_apk_file)

    # 2. 过滤已经成功的pkgs
    all_pkg_list = filter_pkgs(all_pkg_list1, fpath_apk_urls)

    # 3. url获取+下载
    downloader.download_previous_apks(all_pkg_list)
    print('**************************')
    print(f'finish download all!!!!!!')
