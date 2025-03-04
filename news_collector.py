import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime, timedelta
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import os

# 텔레그램 설정
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '7873086292:AAEthtBcUFopzyKY5a3UPBlGdNzP5BrDBIM')
PERSONAL_CHAT_ID = os.environ.get('PERSONAL_CHAT_ID', '7882172599')  # 개인 채팅 ID
CHANNEL_CHAT_ID = os.environ.get('CHANNEL_CHAT_ID', '-1002303882674')  # 채널 ID

# 뉴스 카테고리 및 검색 키워드 설정
NEWS_CATEGORIES = {
    'LLM/AI': {
        'urls': [
            # 네이버 뉴스 - 다양한 검색어로 시도
            'https://search.naver.com/search.naver?where=news&query=인공지능+AI+신규+출시+발표&sort=1&pd=4',
            'https://search.naver.com/search.naver?where=news&query=AI+모델+LLM+새로운&sort=1&pd=4',
            'https://search.naver.com/search.naver?where=news&query=생성형+AI+대형언어모델+발표&sort=1&pd=4',
            'https://search.naver.com/search.naver?where=news&query=AI+기업+신제품+출시&sort=1&pd=4'
        ],
        'selectors': {
            'naver': {
                'article': '.news_wrap',
                'title': '.news_tit',
                'link': '.news_tit',
                'time': '.info_group span:nth-child(3)',
                'press': '.info_group a.press'
            }
        },
        'keywords': [
            'AI', '인공지능', 'LLM', '언어모델', '생성형',
            '출시', '발표', '공개', '새로운', '신규',
            '버전', '업데이트', '개선', '발전'
        ]
    }
}

class NewsCollector:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        
        # Chrome 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    async def get_news(self, url_or_config):
        try:
            if isinstance(url_or_config, dict):
                all_news = set()  # 중복 제거를 위해 set 사용
                
                for url in url_or_config['urls']:
                    try:
                        self.driver.get(url)
                        await asyncio.sleep(2)
                        
                        selectors = url_or_config['selectors']['naver']
                        wait = WebDriverWait(self.driver, 10)
                        articles = wait.until(EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, selectors['article'])
                        ))
                        
                        for article in articles:
                            try:
                                title_element = article.find_element(By.CSS_SELECTOR, selectors['title'])
                                title = title_element.get_attribute('title') or title_element.text
                                link = article.find_element(By.CSS_SELECTOR, selectors['link']).get_attribute('href')
                                
                                time_text = ""
                                try:
                                    time_element = article.find_element(By.CSS_SELECTOR, selectors['time'])
                                    time_text = time_element.text.strip()
                                except:
                                    pass

                                if title and link and any(keyword.lower() in title.lower() for keyword in url_or_config['keywords']):
                                    title_with_time = f"[NAVER] {title}"
                                    if time_text:
                                        title_with_time = f"[NAVER/{time_text}] {title}"
                                    
                                    # 중복 제거를 위해 링크를 기준으로 추가
                                    all_news.add((title_with_time, link))
                                    
                                    if len(all_news) >= 10:
                                        break
                                        
                            except Exception as e:
                                print(f"기사 파싱 중 에러: {e}")
                                continue
                                
                        if len(all_news) >= 10:
                            break
                            
                    except Exception as e:
                        print(f"URL 처리 중 에러: {e}")
                        continue
                
                # set을 list로 변환하고 최신 10개 반환
                return [{'title': title, 'link': link} for title, link in list(all_news)[:10]]
            else:  # 다른 카테고리의 경우
                self.driver.get(url_or_config)
                wait = WebDriverWait(self.driver, 10)
                articles = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.news_area')))
                
                news_list = []
                for article in articles[:10]:
                    try:
                        title_element = article.find_element(By.CSS_SELECTOR, 'a.news_tit')
                        title = title_element.get_attribute('title')
                        link = title_element.get_attribute('href')
                        
                        if title and link:
                            news_list.append({'title': title, 'link': link})
                    except Exception as e:
                        print(f"개별 뉴스 파싱 중 에러: {e}")
                        continue
                
                return news_list
        except Exception as e:
            print(f"뉴스 수집 중 에러: {e}")
            return []

    async def send_telegram_message(self, message):
        # 두 채팅방 모두에 메시지 전송
        await self.bot.send_message(chat_id=PERSONAL_CHAT_ID, text=message, parse_mode='HTML')
        await self.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message, parse_mode='HTML')

    async def collect_and_send(self):
        # KST 기준으로 날짜 설정
        kst = datetime.now() + timedelta(hours=9)  # UTC to KST
        today = kst.strftime('%Y년 %m월 %d일')
        
        full_message = f"📰 {today} 뉴스 요약\n\n"
        
        # AI 뉴스 수집
        for category, url_or_config in NEWS_CATEGORIES.items():
            try:
                news_list = await self.get_news(url_or_config)
                if news_list:
                    full_message += f"━━━ {category} ━━━\n\n"
                    for idx, news in enumerate(news_list, 1):
                        # HTML 특수문자 처리
                        title = news['title'].replace('<', '&lt;').replace('>', '&gt;')
                        full_message += f"{idx}. <a href='{news['link']}'>{title}</a>\n"
                    full_message += "\n"
            except Exception as e:
                print(f"{category} 처리 중 에러 발생: {e}")
                continue
        
        # 인기 뉴스 추가
        popular_news = await self.get_popular_news()
        full_message += f"\n{popular_news}"
        
        # 두 채팅방 모두에 메시지 전송
        await self.bot.send_message(chat_id=PERSONAL_CHAT_ID, text=full_message, parse_mode='HTML')
        await self.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=full_message, parse_mode='HTML')

    async def get_popular_news(self):
        try:
            # 각 언론사별 URL
            press_urls = {
                '연합뉴스': 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=summary&oid=001',
                'KBS': 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=summary&oid=056',
                'MBC': 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=summary&oid=214',
                'YTN': 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=summary&oid=052',
                'JTBC': 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=summary&oid=437'
            }
            
            popular_news = "📰 주요 방송사 뉴스\n\n"
            
            for press, url in press_urls.items():
                try:
                    print(f"Collecting news from {press}...")
                    self.driver.get(url)
                    await asyncio.sleep(3)
                    
                    # 기사 목록 가져오기 - MBC용 셀렉터 추가
                    if press == 'MBC':
                        wait = WebDriverWait(self.driver, 10)
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#main_content .list_body')))
                        articles = self.driver.find_elements(By.CSS_SELECTOR, '#main_content .list_body .type06_headline li, #main_content .list_body .type06 li')
                    else:
                        articles = self.driver.find_elements(By.CSS_SELECTOR, '.type06_headline li, .type06 li')
                    
                    # 각 언론사별 최신 10개 기사 수집
                    popular_news += f"[{press}]\n"
                    news_count = 0
                    collected_titles = set()  # 중복 제거를 위한 set
                    
                    for article in articles:
                        try:
                            title_element = article.find_element(By.CSS_SELECTOR, 'dt:not(.photo) > a')
                            title = title_element.text.strip()
                            link = title_element.get_attribute('href')
                            
                            # 중복 기사 건너뛰기
                            if title in collected_titles:
                                continue
                                
                            if title and link:
                                # HTML 특수문자 처리
                                title = title.replace('<', '&lt;').replace('>', '&gt;')
                                popular_news += f"• <a href='{link}'>{title}</a>\n"
                                news_count += 1
                                collected_titles.add(title)  # 제목 추가
                                
                                if news_count >= 10:
                                    break
                                    
                        except Exception as e:
                            continue
                    
                    popular_news += "\n"
                    
                except Exception as e:
                    print(f"Error collecting news from {press}: {e}")
                    continue
            
            return popular_news
        except Exception as e:
            print(f"주요 뉴스 수집 중 에러: {e}")
            return "주요 뉴스를 가져올 수 없습니다.\n"

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

async def main():
    collector = NewsCollector()
    await collector.collect_and_send()

if __name__ == "__main__":
    asyncio.run(main()) 