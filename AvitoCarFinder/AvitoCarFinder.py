# coding: utf-8-sig
import os
import time
import random
import msvcrt
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import colorama
from colorama import Fore, Style

# Инициализация colorama для поддержки ANSI-цветов
colorama.init(autoreset=True)

# Ссылка с нужными фильтрами (убедитесь, что сортировка по новизне и фильтр по дате применены)
URL = "https://www.avito.ru/voronezh/avtomobili/levyy_rul-ASgBAgICAUTwCqyKAQ?cd=1&f=ASgBAQECA0TwCqyKAfIKsIoB9sQNvrA6AUCE0RJ0iMnaEfzI2hGcydoRksnaEajJ2hGiydoRpsnaEQRF_ikZeyJmcm9tIjpudWxsLCJ0byI6MjUwMDAwfcaaDBt7ImZyb20iOjIwMDAwMCwidG8iOjQwMDAwMH32tg0WeyJmcm9tIjpudWxsLCJ0byI6MTUwffqMFBd7ImZyb20iOjIwMTEsInRvIjpudWxsfQ&radius=200&s=104&searchRadius=200"

def init_driver():
    options = Options()
    options.add_argument("--headless")         # Безголовый режим
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # Отключаем загрузку изображений для экономии трафика
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    # Используем стратегию быстрой загрузки ("eager")
    options.page_load_strategy = "eager"
    service = Service(log_path=os.devnull)
    driver = webdriver.Edge(service=service, options=options)
    return driver

def fetch_page_source(driver, url):
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-marker="item"]'))
        )
    except Exception as e:
        print("Не удалось дождаться загрузки объявлений:", e)
    time.sleep(1)  # Небольшая задержка для полной загрузки
    return driver.page_source

def extract_price(ad):
    # Перебираем все span внутри объявления и возвращаем тот, в котором содержится символ "₽"
    for span in ad.find_all("span"):
        text = span.get_text(" ", strip=True)
        if "₽" in text:
            return text
    return "Неизвестно"

def parse_listings(html):
    soup = BeautifulSoup(html, 'html.parser')
    ads = soup.select('div[data-marker="item"]')
    results = []
    for ad in ads:
        ad_id = ad.get("data-item-id")
        title_tag = ad.find("h3")
        if not title_tag:
            title_tag = ad.find("a", {"data-marker": "item-title"})
        title = title_tag.get_text(strip=True) if title_tag else "Без названия"
        link_tag = ad.find("a", {"data-marker": "item-title"})
        ad_url = "https://www.avito.ru" + link_tag.get("href") if link_tag and link_tag.get("href") else None
        # Извлекаем время публикации объявления
        time_tag = ad.find(attrs={"data-marker": "item-date"})
        ad_time_text = time_tag.get_text(strip=True) if time_tag else "Неизвестно"
        # Извлекаем цену
        price = extract_price(ad)
        
        results.append({
            "id": ad_id,
            "title": title,
            "url": ad_url,
            "time_text": ad_time_text,
            "price": price
        })
    return results

def parse_relative_time(time_text):
    """Парсит время вида '15 секунд назад', '5 минут назад', '2 часа назад', 'сегодня', 'вчера'."""
    now = datetime.now()
    text = time_text.lower()
    try:
        if "секунд" in text:
            seconds = int(text.split()[0])
            return now - timedelta(seconds=seconds)
        elif "минут" in text:
            minutes = int(text.split()[0])
            return now - timedelta(minutes=minutes)
        elif "час" in text:
            hours = int(text.split()[0])
            return now - timedelta(hours=hours)
        elif "сегодня" in text:
            return datetime(now.year, now.month, now.day)
        elif "вчера" in text:
            yesterday = now - timedelta(days=1)
            return datetime(yesterday.year, yesterday.month, yesterday.day)
    except Exception:
        return None
    return None

def filter_recent_ads(ads, max_age_hours=24):
    now = datetime.now()
    filtered = []
    for ad in ads:
        ad_time = parse_relative_time(ad["time_text"])
        if ad_time and (now - ad_time).total_seconds() <= max_age_hours * 3600:
            filtered.append(ad)
    return filtered

def main():
    driver = init_driver()
    seen_ads = {}  # Словарь для запоминания объявлений по ID
    emergency_mode = False  # Режим проверки: False - стандартный, True - экстренный (фикс. 30 сек)
    
    # Начальная загрузка: собираем и запоминаем все свежие объявления (до 24 часов)
    print(f"\nНачальная загрузка объявлений: {datetime.now()}")
    html = fetch_page_source(driver, URL)
    ads = parse_listings(html)
    recent_ads = filter_recent_ads(ads, max_age_hours=24)
    for ad in recent_ads:
        seen_ads[ad["id"]] = ad
    # Выводим запомненные объявления жёлтым цветом
    print(f"{Fore.YELLOW}Запомненные объявления (свежих до 24 часов):{Style.RESET_ALL}")
    for ad in seen_ads.values():
        print(f"{Fore.YELLOW}Объявление: {ad['title']} | {ad['price']} | {ad['url']} | {ad['time_text']}{Style.RESET_ALL}")
    
    # Основной цикл проверки новых объявлений
    while True:
        print(f"\nПроверка новых объявлений: {datetime.now()}")
        html = fetch_page_source(driver, URL)
        ads = parse_listings(html)
        recent_ads = filter_recent_ads(ads, max_age_hours=24)
        new_ads = []
        for ad in recent_ads:
            if ad["id"] not in seen_ads:
                new_ads.append(ad)
                seen_ads[ad["id"]] = ad
        if new_ads:
            print(f"{Fore.RED}Найдены новые объявления:{Style.RESET_ALL}")
            for ad in new_ads:
                print(f"{Fore.RED}Объявление: {ad['title']} | {ad['price']} | {ad['url']} | {ad['time_text']}{Style.RESET_ALL}")
        else:
            print("Новых объявлений не найдено.")
        
        # Определяем задержку между проверками в зависимости от режима
        if emergency_mode:
            delay = 30
        else:
            delay = 30 if random.random() < 0.5 else random.randint(30, 300)
        print(f"Следующая проверка через {delay} секунд. (Нажмите ↑ для экстренного режима, ↓ для стандартного)")
        
        elapsed = 0
        skip_wait = False
        while elapsed < delay:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b'\xe0':  # Специальная клавиша
                    ch2 = msvcrt.getch()
                    if ch2 == b'H':  # Стрелка вверх
                        emergency_mode = True
                        print(f"{Fore.CYAN}Экстренный режим включен, немедленная проверка.{Style.RESET_ALL}")
                        skip_wait = True
                        break
                    elif ch2 == b'P':  # Стрелка вниз
                        emergency_mode = False
                        print(f"{Fore.CYAN}Режим по умолчанию включен.{Style.RESET_ALL}")
            time.sleep(0.5)
            elapsed += 0.5
        if skip_wait:
            continue  # Прерываем ожидание и начинаем новую проверку сразу

if __name__ == "__main__":
    main()
