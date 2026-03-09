from ast_parser import ASTParser


def test_ast_polyglot():
    parser = ASTParser()
    print("Languages loaded:", parser.langs.keys())

    # 1. Pure Python Test
    py_code = """
def login_user(username: str):
    user = db_session.query(User).filter_by(username).first()
    request_backend("POST", "/api/auth")
    return user
    """
    py_graph = parser.parse_file("auth.py", py_code)
    print("\n--- Python Graph ---")
    print("Defined:", py_graph["functions_defined"])
    print("Called:", py_graph["functions_called"])

    # 2. Vue/TS Test (Simulating Elastro/ReleaseFlow Frontend logic)
    ts_code = """
const updateSettings = async () => {
    logger.info("Updating settings...")
    const res = await axios.post("/api/settings", payload)
    handleResponse(res)
}
    """
    ts_graph = parser.parse_file("UserSettings.vue", ts_code)
    print("\n--- Vue/TS Graph ---")
    print("Defined:", ts_graph["functions_defined"])
    print("Called:", ts_graph["functions_called"])


if __name__ == "__main__":
    test_ast_polyglot()
