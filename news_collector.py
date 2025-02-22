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

# 텔레그램 설정
TELEGRAM_TOKEN = "7873086292:AAEthtBcUFopzyKY5a3UPBlGdNzP5BrDBIM"
CHAT_ID = "7882172599"

# 뉴스 카테고리 및 검색 키워드 설정
NEWS_CATEGORIES = {
    'LLM/AI': {
        'urls': [
            # 네이버 뉴스만 우선 사용
            'https://search.naver.com/search.naver?where=news&query=AI+인공지능+ChatGPT&sort=1&pd=4',
        ],
        'selectors': {
            'naver': {
                'article': '.news_wrap',
                'title': '.news_tit',
                'link': '.news_tit',
                'time': '.info_group span:nth-child(3)'
            }
        },
        'keywords': [
            'GPT', 'AI', '인공지능', 'LLM', 'Claude', 'Gemini',
            'ChatGPT', '생성형', '챗봇', '머신러닝', '딥러닝'
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
                all_news = []
                
                for url in url_or_config['urls']:
                    try:
                        self.driver.get(url)
                        await asyncio.sleep(2)
                        
                        # URL에 따른 셀렉터 선택
                        selector_key = 'naver' if 'naver.com' in url else \
                                     'daum' if 'daum.net' in url else \
                                     'aitimes' if 'aitimes.com' in url else 'naver'
                        
                        selectors = url_or_config['selectors'][selector_key]
                        wait = WebDriverWait(self.driver, 10)
                        articles = wait.until(EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, selectors['article'])
                        ))
                        
                        # LLM/AI 뉴스는 10개까지 수집
                        for article in articles[:15]:  # 여유있게 15개 검사
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

                                source = 'NAVER' if 'naver.com' in url else \
                                        'DAUM' if 'daum.net' in url else \
                                        'AI타임스' if 'aitimes.com' in url else ''
                                
                                if title and link and any(keyword.lower() in title.lower() for keyword in url_or_config['keywords']):
                                    title_with_time = f"[{source}] {title}"
                                    if time_text:
                                        title_with_time = f"[{source}/{time_text}] {title}"
                                    
                                    print(f"Found news: {title_with_time}")
                                    all_news.append({
                                        'title': title_with_time,
                                        'link': link
                                    })
                            except Exception as e:
                                print(f"기사 파싱 중 에러: {e}")
                                continue
                    except Exception as e:
                        print(f"URL 처리 중 에러 ({url}): {e}")
                        continue
                
                return all_news[:10]  # 최대 10개 반환
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
                            print(f"Found news: {title}")
                            news_list.append({'title': title, 'link': link})
                    except Exception as e:
                        print(f"개별 뉴스 파싱 중 에러: {e}")
                        continue
                
                return news_list
        except Exception as e:
            print(f"뉴스 수집 중 에러: {e}")
            return []

    async def send_telegram_message(self, message):
        await self.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML')

    async def collect_and_send(self):
        today = datetime.now().strftime('%Y년 %m월 %d일')
        full_message = f"📰 {today} 뉴스 요약\n\n"
        
        # AI 뉴스 수집
        for category, url_or_config in NEWS_CATEGORIES.items():
            try:
                news_list = await self.get_news(url_or_config)
                if news_list:
                    full_message += f"━━━ {category} ━━━\n\n"
                    for idx, news in enumerate(news_list, 1):
                        title = news['title'].replace('<', '').replace('>', '')
                        # 링크를 제목에 포함
                        full_message += f"{idx}. <a href='{news['link']}'>{title}</a>\n"
                    full_message += "\n"
            except Exception as e:
                print(f"{category} 처리 중 에러 발생: {e}")
                continue
        
        # 인기 뉴스 추가
        popular_news = await self.get_popular_news()
        full_message += f"\n{popular_news}"
        
        # 메시지 길이 제한
        if len(full_message) > 4000:
            full_message = full_message[:4000] + "\n\n... (더 많은 뉴스가 있습니다)"
        
        # HTML 모드 다시 활성화
        await self.bot.send_message(chat_id=CHAT_ID, text=full_message, parse_mode='HTML')

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
                    self.driver.get(url)
                    await asyncio.sleep(1)
                    wait = WebDriverWait(self.driver, 10)
                    
                    # 모든 기사 목록 가져오기
                    articles = []
                    for selector in ['.type06_headline li', '.type06 li']:
                        articles.extend(wait.until(EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, selector)
                        )))
                    
                    # 각 언론사별 최신 5개 텍스트 기사 수집
                    popular_news += f"[{press}]\n"  # 언론사 제목 추가
                    news_count = 0
                    for article in articles:
                        try:
                            # 동영상 기사 제외
                            if '동영상' in article.text:
                                continue
                                
                            title_element = article.find_element(By.CSS_SELECTOR, 'dt:not(.photo) > a')
                            title = title_element.text.strip()
                            link = title_element.get_attribute('href')
                            
                            if title and link:
                                title = title.replace('<', '').replace('>', '')
                                popular_news += f"• <a href='{link}'>{title}</a>\n"
                                news_count += 1
                                
                                if news_count >= 5:  # 5개 수집하면 중단
                                    break
                                    
                        except Exception as e:
                            continue
                    
                    popular_news += "\n"  # 언론사 구분을 위한 빈 줄
                    
                except Exception as e:
                    continue
            
            return popular_news
        except Exception as e:
            print(f"주요 뉴스 수집 중 에러: {e}")
            return "주요 뉴스를 가져올 수 없습니다.\n"

    async def get_google_news(self):
        try:
            url = "https://news.google.com/search?q=AI%20LLM%20GPT%20when:1d&hl=ko&gl=KR"
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 10)
            
            # 페이지 로드 대기
            await asyncio.sleep(3)
            
            # 구글 뉴스 목록 가져오기
            articles = wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, 'article.MQsxIb.xTewfe.R7GTQ.keNKEd.j7vNaf.Cc0Z5d.EjqUne')
            ))
            
            google_news = "🌏 해외 AI 뉴스\n\n"
            
            for idx, article in enumerate(articles[:10], 1):
                try:
                    title_element = article.find_element(By.CSS_SELECTOR, 'a.DY5T1d.RZIKme')
                    title = title_element.text
                    link = title_element.get_attribute('href')
                    
                    if title and link:
                        # 영어 기사만 필터링 (선택사항)
                        if any(c.isascii() for c in title):
                            google_news += f"{idx}. <a href='{link}'>{title}</a>\n"
                except Exception as e:
                    print(f"구글 뉴스 파싱 중 에러: {e}")
                    continue
            
            google_news += "\n"
            return google_news
        except Exception as e:
            print(f"구글 뉴스 수집 중 에러: {e}")
            print(f"에러 상세: {str(e)}")
            try:
                print("\nPage source:")
                print(self.driver.page_source[:1000])  # 페이지 소스 출력
            except:
                pass
            return "해외 뉴스를 가져올 수 없습니다.\n"

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

async def main():
    collector = NewsCollector()
    await collector.collect_and_send()

if __name__ == "__main__":
    asyncio.run(main()) 