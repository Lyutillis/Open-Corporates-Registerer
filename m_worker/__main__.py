import asyncio
from typing import List
import json
from dataclasses import asdict
from playwright.async_api import (
    async_playwright,
    Playwright,
    Browser,
    Page
)
import string
import random
from twocaptcha import TwoCaptcha
from concurrent import futures

from utils.dto import User, Task, Result
from utils.cache import AsyncCache
from utils.log import get_logger
import envs


BASE_URL = "https://opencorporates.com/"
MAIL_URL = "https://www.guerrillamail.com/inbox"

worker_logger = get_logger("Worker")


class Worker:
    def __init__(self) -> None:
        self.tasks: List[Task] = []
        self.results: List[Result] = []
        self.cache_1: AsyncCache = AsyncCache(1)

        self.asyncio_tasks: List[asyncio.Task] = []
        self.max_tasks: int = 2

        self.playwright: Playwright = None
        self.browser: Browser = None

    async def get_tasks(self) -> None:
        worker_logger.info("Getting tasks from Redis")
        redis_result = await self.cache_1.red.rpop("tasks_queue")
        while redis_result:
            self.tasks.append(
                Task(
                    **json.loads(redis_result)
                )
            )
            redis_result = await self.cache_1.red.rpop("tasks_queue")

    async def save_results(self) -> None:
        worker_logger.info("Passing results to Redis")
        for result in self.results[:]:
            await self.cache_1.red.lpush(
                "results_queue",
                json.dumps(asdict(result))
            )
            self.results.remove(result)

    async def start_playwright(self) -> None:
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
        )
        worker_logger.info("Started Playwright")

    async def stop_playwright(self) -> None:
        await self.browser.close()
        await self.playwright.stop()
        worker_logger.info("Playwright was shut down")

    def clean_asyncio_tasks(self) -> None:
        for task in self.asyncio_tasks:
            if task.done():
                self.asyncio_tasks.remove(task)

    async def run_task(self, task: Task) -> None:
        worker_logger.info("Launched task")
        context = await self.browser.new_context()
        main_page = await context.new_page()
        mail_page = await context.new_page()
        try:
            user = await self.create_account(main_page, mail_page)
            self.results.append(
                Result(
                    task_id=task.id,
                    user=user
                )
            )
        finally:
            await main_page.close()
            await mail_page.close()
            await context.close()

    async def accept_cookies(self, page: Page) -> None:
        await page.locator(
            "//div[@class='cky-notice-btn-wrapper']"
            "//button[contains(@class, 'cky-btn-accept')]"
        ).click()

    async def get_email(self, page: Page) -> str:
        return await page.locator(
            "//span[@id='email-widget']"
        ).text_content()

    def get_random_str(self, length: int) -> str:
        return "".join(
            random.choices(string.ascii_lowercase + string.digits, k=length)
        )

    async def solve_captcha(self, page: Page) -> None:
        solver = TwoCaptcha(envs.API_KEY)
        sitekey = await page.locator(
            "//div[@class='g-recaptcha ']"
        ).get_attribute("data-sitekey")
        url = page.url
        worker_logger.info("Solving Captcha")
        try:
            result = await asyncio.to_thread(solver.recaptcha, sitekey, url)
        except Exception as e:
            worker_logger.info(e)
        else:
            return result.get("code")

    async def fill_in_form(self, page: Page, user: User) -> None:
        await page.locator("//input[@id='user_name']").fill(user.username)
        await page.locator("//input[@id='user_email']").fill(user.email)
        await page.locator(
            "//input[@id='user_user_info_job_title']"
        ).fill(user.job_title)
        await page.locator(
            "//input[@id='user_user_info_company']"
        ).fill(user.organization)
        await page.locator("//input[@id='user_password']").fill(user.password)
        await page.locator(
            "//input[@id='user_password_confirmation']"
        ).fill(user.password)

        await page.locator("//div[@class='terms-conditions-box']").click()
        await page.mouse.wheel(0, 7000)

        await page.locator(
            "//input[@class='terms-conditions-checkbox']"
        ).check()

    async def create_account(
        self,
        main_page: Page,
        mail_page: Page
    ) -> User:
        await main_page.goto(BASE_URL)
        await mail_page.goto(MAIL_URL)

        await self.accept_cookies(main_page)

        await main_page.locator("//*[@id='menu-item-6720']//a").click()
        await main_page.locator(
            "//a[contains(@class, 'register-link')]"
        ).click()

        mail = await self.get_email(mail_page)

        user = User(
            email=mail,
            username=mail.split("@")[0],
            job_title=self.get_random_str(7),
            organization=self.get_random_str(7),
            password=mail,
        )

        await self.fill_in_form(main_page, user)

        result = await self.solve_captcha(main_page)

        await main_page.evaluate(
            "document.getElementById('g-recaptcha-response')"
            f".innerHTML = '{result}'"
        )

        await main_page.get_by_text("Register new account").click()

        worker_logger.info("Waiting on the email")

        await mail_page.locator(
            "(//tr[not(@id='mr_1')]//span)[1]"
        ).click()
        await mail_page.locator("//*[@class='email_body']//p//a").click()

        return user

    async def run(self) -> None:
        await self.start_playwright()

        try:
            while True:
                await self.get_tasks()

                self.clean_asyncio_tasks()

                if len(self.asyncio_tasks) < self.max_tasks:
                    if self.tasks:
                        task = self.tasks.pop()
                        self.asyncio_tasks.append(
                            asyncio.create_task(
                                self.run_task(task)
                            )
                        )

                await self.save_results()
                await asyncio.sleep(20)
        finally:
            await asyncio.gather(*self.asyncio_tasks)

            await self.stop_playwright()

            worker_logger.info("Worker terminated.")


async def main() -> None:
    worker = Worker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
