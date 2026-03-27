#imports
from collectors.notice import fetch_notice_list


# app/main.py
def main():
    notices = fetch_notice_list()

    print("=== 공지사항 목록 ===")
    for notice in notices:
        print(f"제목 : {notice['title']}")
        print(f"URL : {notice['url']}")
        print("-" * 50)



if __name__ == "__main__":
    print("Start the application - MABIMO BOT\n")
    main()
