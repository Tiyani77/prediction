
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="YANIDOLLARZ",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark theme styling
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(
            135deg,
            #080D15,
            #101C2B,
            #17263A
        );
        color: white;
    }

    .block-container {
        padding-top: 3rem;
        max-width: 1200px;
    }

    h1, h2, h3 {
        color: #F8FAFC !important;
    }

    .stButton > button[kind="primary"] {
        background-color: #2563EB;
        color: white;
        border: none;
        border-radius: 9px;
    }

    .stButton > button {
        border-radius: 9px;
    }
</style>
""", unsafe_allow_html=True)

# App name
st.markdown(
    "<h2>YANI<span style='color:#3B82F6;'>DOLLARZ</span></h2>",
    unsafe_allow_html=True
)

st.write("FOOTBALL PREDICTIONS & ANALYTICS")

st.divider()

# Remember which screen is selected
if "page" not in st.session_state:
    st.session_state.page = "home"

def navigate(page):
    st.session_state.page = page

# Homepage
if st.session_state.page == "home":

    st.title("SMARTER PREDICTIONS.")
    st.title("BETTER DECISIONS.")

    st.write(
        "Football match predictions, statistical analysis "
        "and risk insights for goals, corners, bookings and more."
    )

    st.write("")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login", type="primary", use_container_width=True):
            navigate("login")
            st.rerun()

    with col2:
        if st.button("Create Account", use_container_width=True):
            navigate("register")
            st.rerun()

# Login screen
elif st.session_state.page == "login":

    st.header("Welcome Back")

    with st.form("login_form"):
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")

        remember = st.checkbox("Remember me")

        login = st.form_submit_button(
            "Login",
            type="primary",
            use_container_width=True
        )

        if login:
            st.info("Authentication will be connected in the next stage.")

    st.divider()

    if st.button("Continue with Google", use_container_width=True):
        st.info("Google sign-in will be configured later.")

    if st.button("Create an Account"):
        navigate("register")
        st.rerun()

    if st.button("Back to Home"):
        navigate("home")
        st.rerun()

# Registration screen
elif st.session_state.page == "register":

    st.header("Create Your Account")

    with st.form("register_form"):

        username = st.text_input("Username")
        email = st.text_input("Email Address")
        password = st.text_input("Create Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")

        register = st.form_submit_button(
            "Create Account",
            type="primary",
            use_container_width=True
        )

        if register:
            if not username or not email or not password:
                st.warning("Please complete all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                st.info("Account creation will be connected later.")

    if st.button("Already have an account? Login"):
        navigate("login")
        st.rerun()

    if st.button("Back to Home"):
        navigate("home")
        st.rerun()

