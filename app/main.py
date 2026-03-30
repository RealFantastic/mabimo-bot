#imports
from collectors.notice import fetch_notice_list


# app/main.py
def main():
    notices = fetch_notice_list()

    print("=== 공지사항 목록 ===")
    for notice in notices:
        print(f"글번호 : {notice['thread_id']}")
        print(f"제목 : {notice['title']}")
        print(f"분류 : {notice['category']}")
        print(f"날짜 : {notice['published_at']}")
        print(f"URL : {notice['url']}")
        print("-" * 50)



if __name__ == "__main__":
    print("Start the application - MABIMO BOT\n")
    main()
