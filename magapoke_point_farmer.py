import time
import random
import pickle
import os
import base64
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

class MagapokePointFarmer:
    def __init__(self, headless=False):
        self.options = Options()
        self.options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')
        
        # GitHub Actions環境(CI=true)またはheadless引数がTrueなら画面なしモード
        if headless or os.getenv("CI"):
            print("   [System] Headlessモードで起動します")
            self.options.add_argument('--headless')
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
        
        self.options.add_argument('--window-size=375,812')

        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=self.options
        )
        self.wait = WebDriverWait(self.driver, 10)
        self.cookie_file = "magapoke_cookies.pkl"

    def save_cookies(self):
        """現在のCookieをファイルに保存(ローカル実行時のみ有効)"""
        # CI環境ではファイル保存しても次回に持ち越せないのでログだけ出すか、アーティファクト保存が必要
        # 今回は簡易化のためローカルのみ想定
        if not os.getenv("CI"):
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(self.driver.get_cookies(), f)
            print(f"   [System] ログイン情報を {self.cookie_file} に保存しました。")

    def load_cookies(self, target_url):
        """Cookieを読み込む（ファイル優先、なければ環境変数）"""
        self.driver.get(target_url) 
        time.sleep(1)

        # 1. 環境変数 (GitHub Actions用) からの読み込み
        env_cookies = os.getenv("MAGAPOKE_COOKIES_BASE64")
        if env_cookies:
            print("   [System] 環境変数からCookieを復元しています...")
            try:
                # Base64文字列をデコードしてpickleとしてロード
                decoded = base64.b64decode(env_cookies)
                cookies = pickle.loads(decoded)
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception:
                        pass
                self.driver.refresh()
                time.sleep(3)
                return True
            except Exception as e:
                print(f"   [Error] 環境変数のCookie復元に失敗: {e}")

        # 2. ローカルファイルからの読み込み
        if os.path.exists(self.cookie_file):
            print("   [System] ローカルファイルからCookieを読み込んでいます...")
            try:
                with open(self.cookie_file, 'rb') as f:
                    cookies = pickle.load(f)
                    for cookie in cookies:
                        try:
                            self.driver.add_cookie(cookie)
                        except Exception:
                            pass 
                self.driver.refresh()
                time.sleep(3)
                return True
            except Exception as e:
                print(f"   [Warning] Cookie読み込み中にエラー: {e}")
                return False
        
        return False

    def smart_read(self):
        try:
            viewer_el = self.driver.find_element(By.CSS_SELECTOR, ".c-viewer")
            class_list = viewer_el.get_attribute("class")

            if "is-vertical" in class_list:
                print("      -> ℹ️ 判定: 縦読みモード")
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                self._read_vertical(scroll_height)
            else:
                print("      -> ℹ️ 判定: 横読みモード")
                self._read_horizontal()

            print("      -> ✅ 読了動作完了。判定通信待ち...")
            time.sleep(4) 

        except Exception as e:
            print(f"      -> [Warning] 読み方判定エラー: {e}")
            self._read_horizontal()

    def _read_vertical(self, total_height):
        print("      -> 📖 [縦読み] スクロール開始...")
        current_position = 0
        while current_position < total_height:
            scroll_step = random.randint(300, 700)
            current_position += scroll_step
            self.driver.execute_script(f"window.scrollTo(0, {current_position});")
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            time.sleep(random.uniform(0.5, 1.2))

    def _read_horizontal(self):
        print("      -> 📖 [横読み] ページめくり開始...")
        try:
            pages = self.driver.find_elements(By.CSS_SELECTOR, ".c-viewer__pages-item")
            total_pages = len(pages)
            print(f"      -> 📄 総ページ数: {total_pages}")
        except:
            total_pages = 25 

        for i in range(total_pages):
            print(f"         ... {i+1}/{total_pages}")
            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, ".c-viewer__pager-next")
                self.driver.execute_script("arguments[0].click();", next_btn)
            except:
                try:
                    action = ActionChains(self.driver)
                    window_width = self.driver.execute_script("return window.innerWidth")
                    window_height = self.driver.execute_script("return window.innerHeight")
                    tap_x = int(window_width * 0.1) 
                    tap_y = int(window_height * 0.5)
                    action.move_by_offset(tap_x, tap_y).click().perform()
                    action.reset_actions()
                    action.move_to_element_with_offset(self.driver.find_element(By.TAG_NAME, 'body'), 0, 0)
                except:
                    pass
            time.sleep(random.uniform(0.6, 1.2))
        print("      -> 🏁 めくり完了")

    def collect_and_read(self, target_list_url):
        visited_urls = set()
        try:
            # ログイン試行
            if not self.load_cookies(target_list_url):
                # CI環境でログインできない場合はエラー終了（対話入力できないため）
                if os.getenv("CI"):
                    print("[Error] CI環境ですがCookieが設定されていないか無効です。")
                    print("SecretsのMAGAPOKE_COOKIES_BASE64を確認してください。")
                    return

                print(f"ページへ移動: {target_list_url}")
                self.driver.get(target_list_url)
                print("\n" + "="*60)
                print("【初回ログインが必要です】")
                input(">> ログイン完了後に Enter: ")
                self.save_cookies()
            else:
                print("   [System] ログイン状態で開始します。")

            # 巡回ループ
            loop_count = 0
            while True:
                # 無限ループ防止（最大5周など）
                if loop_count > 5:
                    break
                loop_count += 1
                
                print(f"\n🏠 ホーム({target_list_url})チェック...")
                self.driver.get(target_list_url)
                time.sleep(5) 

                point_items = self.driver.find_elements(By.CSS_SELECTOR, "a.c-point-item")
                episode_queue = []
                for item in point_items:
                    try:
                        url = item.get_attribute("href")
                        if url and (url not in visited_urls):
                            title = item.text.replace("\n", " ")[:20]
                            episode_queue.append({"url": url, "title": title})
                    except:
                        continue

                if not episode_queue:
                    print("\n🎉 未読エピソードはありません。終了します。")
                    break

                print(f"🎯 {len(episode_queue)} 件の未読を発見。")

                for i, ep in enumerate(episode_queue):
                    print(f"[{i+1}/{len(episode_queue)}] 『{ep['title']}』")
                    self.driver.get(ep['url'])
                    time.sleep(3)
                    self.smart_read()
                    visited_urls.add(ep['url'])
                    self.save_cookies()
                    time.sleep(random.uniform(2, 5))

                print("🔄 ホームに戻ります...")
                time.sleep(2)

        except Exception as e:
            print(f"\n[Error] {e}")
        finally:
            print("処理終了")
            self.driver.quit()

if __name__ == "__main__":
    TARGET_URL = "https://pocket.shonenmagazine.com/" 
    bot = MagapokePointFarmer(headless=False)
    bot.collect_and_read(TARGET_URL)