# -*- coding: utf-8 -*-
import scrapy
import re
import base64
import time
import random
from PIL import Image
from io import BytesIO
from selenium import webdriver
from selenium.webdriver import ActionChains
try:
    import urlparse as parse
except:
    from urllib import parse
from scrapy.loader import ItemLoader
from zhihu_spider.items import ZhihuQuestionItem, ZhihuAswerItem


class ZhihuSpider(scrapy.Spider):
    name = 'zhihu'
    allowed_domains = ['www.zhihu.com']
    start_urls = ['http://www.zhihu.com/']

    headers = {
        'HOST': 'www.zhihu.com',
        'Referer': 'https://www.zhihu.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
    }

    def parse(self, response):
        """
        提取出html页面中的所有url，并跟踪这些url进行一步爬取
        如果提取的url中格式为/question/xxx就下载之后直接进入解析函数
        """
        all_urls = response.css('a::attr(href)').extract()
        all_urls = [parse.urljoin(response.url, url) for url in all_urls]
        all_urls = filter(lambda x: True if x.startswith('https') else False, all_urls)
        for url in all_urls:
            match_obj = re.match('(.*zhihu.com/question/(\d+))(/|$).*', url)
            if match_obj:
                request_url = match_obj.group(1)
                question_id = match_obj.group(2)

                yield scrapy.Request(request_url,
                                     headers=self.headers,
                                     callback=self.parse_question)

    # 处理question页面，从页面中提取出具体的question item
    def parse_question(self, response):
        match_obj = re.match('(.*zhihu.com/question/(\d+))(/|$).*', response.url)
        if match_obj:
            question_id = int(match_obj.group(2))
        item_loader = ItemLoader(item=ZhihuQuestionItem(), response=response)
        if 'QuestionHeader-title' in response.text:
            # 处理新版本
            item_loader.add_css('title', 'h1.QuestionHeader-title::text')
            item_loader.add_css('content', '.QuestionHeader-detail')
            item_loader.add_value('url', response.url)
            item_loader.add_value('zhihu_id', question_id)
            item_loader.add_css('answer_num', '.List-headerText span::text')
            item_loader.add_css('comments_num', '.QuestionHeader-Comment button::text')
            item_loader.add_css('watch_user_num', '.NumberBoard-itemValue::text')
            item_loader.add_css('topics', '.QuestionHeader-topics .Popover::text')

            question_item = item_loader.load_item()
        else:
            # 处理知乎旧版本
            item_loader.add_css('title', '.zh-question-title h2 a::text')
            item_loader.add_css('content', '#zh-question-detail')
            item_loader.add_value('url', response.url)
            item_loader.add_value('zhihu_id', question_id)
            item_loader.add_css('answer_num', '#zh-question-answer-num::text')
            item_loader.add_css('comments_num', '#zh-question-meta-wrap a[name="addcomment"]::text')
            item_loader.add_css('watch_user_num', '#zh-question-side-header-wrap::text')
            item_loader.add_css('topics', '.zm-tag-editor-labels a::text')

            question_item = item_loader.load_item()
        pass

    def start_requests(self):
        login_url = 'https://www.zhihu.com/signup'
        browser = webdriver.Firefox()
        browser.get(login_url)
        # 切换到登陆
        browser.find_element_by_xpath("//div[@class ='SignContainer-switch']/span").click()
        # 输入账号
        browser.find_element_by_name("username").send_keys("13027146128")
        # 输入密码
        browser.find_element_by_name("password").send_keys("pcz930301")
        # 得到验证码元素
        captcha_element = browser.find_element_by_xpath("//form[@class='SignFlow']/div[3]//img")
        # 得到验证码的base64编码
        captcha_base64 = captcha_element.get_attribute('src')
        # 如果有验证码：
        if captcha_base64 != 'data:image/jpg;base64,null':
            # 得到验证码图片的base64编码
            captcha_image = captcha_base64.split(',')[-1]
            # 将图片的base64编码解码
            captcha_data = base64.b64decode(captcha_image)
            # 读取图片
            image = Image.open(BytesIO(captcha_data))
            # 显示图片
            image.show()
            # 得到验证码类型
            captcha_type = captcha_element.get_attribute('class')
            # 如果是英文验证码：
            if captcha_type == 'Captcha-englishImg':
                # 输入验证码字符
                captcha_code = input('请输入图片中的验证码：')
                browser.find_element_by_name("captcha").send_keys(captcha_code)
            else:
                # 输入坐标，鼠标模拟点击, 每个字宽度约 (160.5-5.5)/7=22, 每个字高度范围：13.5———35.5
                captcha_code = input('请输入倒立文字的序号（以‘,’分割）：')
                # 得到序号
                captcha_serial_nums = captcha_code.split(',')
                for captcha_serial_num in captcha_serial_nums:
                    # 得到字符的位置
                    x = 5.5 + (int(captcha_serial_num) - 1) * 22 + random.uniform(10, 20)
                    y = random.uniform(15, 30)
                    # 鼠标点击的位置
                    click_pos = (x, y)
                    # 将鼠标移动到指定位置
                    ActionChains(browser).move_to_element_with_offset(captcha_element, x, y).perform()
                    # 点击鼠标
                    ActionChains(browser).click().perform()
        # 点击登陆按钮
        browser.find_element_by_xpath("//button[@type='submit']").click()
        time.sleep(2)  # 等待登陆跳转
        # 如果登陆title包含“首页”，登陆成功
        if re.search(r'首页', browser.title):
            print('登陆成功！！')
            cookies = browser.get_cookies()
            browser.close()
            for url in self.start_urls:
                yield scrapy.Request(url, dont_filter=True, headers=self.headers, cookies=cookies)
        else:
            print("登陆失败！")
            browser.close()

    # def start_requests(self):
    #     return [scrapy.Request('https://www.zhihu.com/#signin',
    #                            headers=self.headers,
    #                            callback=self.login)]

    # def login(self, response):
    #     response_text = response.text
    #     match_obj = re.match('.*name="_xsrf" value="(.*?)"', response_text, re.DOTALL)
    #     xrsf = ''
    #     if match_obj:
    #         xrsf = match_obj.group(1)
    #         return [scrapy.FormRequest(
    #             url='https://www.zhihu.com/login/phone_num',
    #             formdata={
    #                 '_xsrf': xrsf,
    #                 'phone_num': 13027146128,
    #                 'password': 'pcz930301'
    #             },
    #             headers=self.headers,
    #             callback=self.check_login
    #         )]

    # # 验证服务器的返回数据判断是否成功
    # def check_login(self, response):
    #     text_json = json.load(response.text)
    #     if "msg" in text_json and text_json['msg'] == '登陆成功':
    #         for url in self.start_urls:
    #             yield scrapy.Request(url, dont_filter=True, headers=self.headers)
