"""Entry point for terminal chat mode."""
from api.chat_service import process_user_message


def run_chat():
    print("AI Data Analyst Ready. Type 'exit' to quit.\n")
    session_id = "terminal-session"

    while True:
        user_input = input("User: ")

        if user_input.lower() == "exit":
            break

        response = process_user_message(session_id=session_id, user_input=user_input)
        final_message = response["assistant_text"]

        print("\nAI:", final_message, "\n")


if __name__ == "__main__":
    run_chat()