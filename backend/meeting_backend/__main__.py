import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', choices=['127.0.0.1', '::1'], default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run('meeting_backend.app:create_app', factory=True, host=args.host, port=args.port, access_log=False)


if __name__ == '__main__':
    main()
