
import streamlit as st

# ==========================================
# YANIDOLLARZ - FOOTBALL PREDICTION PLATFORM
# ==========================================

# Page configuration
st.set_page_config(
    page_title="YANIDOLLARZ",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 1. WEBSITE DESIGN
# ==========================================

st.markdown("""
<style>

/* Main background */
.stApp {
    background: linear-gradient(
        135deg,
        #080D15 0%,
        #101C2B 50%,
        #17263A 100%
    );
    color: #F8FAFC;
}

/* Main content */
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1250px;
}

/* Headings */
h1, h2, h3 {
    color: #F8FAFC !important;
}

/* Paragraph text */
p {
    color: #E2E8F0;
}

/* All buttons */
.stButton > button {
    background-color: #1B2A40;
    color: #FFFFFF !important;
    border: 1px solid #3B82F6;
    border-radius: 9px;
    font-weight: 600;
    min-height: 45px;
    transition: 0.2s ease;
}

/* Button hover */
.stButton > button:hover {
    background-color: #263B58;
    color: #FFFFFF !important;
    border-color: #60A5FA;
}

/* Primary buttons */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background-color: #2563EB;
    color: #FFFFFF !important;
    border: none;
    border-radius: 9px;
}

/* Primary button hover */
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
    background-color: #1D4ED8;
    color: #FFFFFF !important;
}

/* Form submit buttons */
.stFormSubmitButton > button {
    color: #FFFFFF !important;
    border-radius: 9px;
}

/* Input fields */
.stTextInput input {
    background-color: #162337;
    color: #FFFFFF;
    border: 1px solid #334155;
    border-radius: 8px;
}

/* Input labels */
.stTextInput label {
    color: #E2E8F0 !important;
}

/* Dividers */
hr {
    border-color: #334155;
}

/* Hide Streamlit footer */
footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. SESSION STATE AND NAVIGATION
# ==========================================

if "page" not in st.session_state:
    st.session_state.page = "home"


def navigate(page):
    st.session_state.page = page
    st.rerun()


# ==========================================
# 3. WEBSITE HEADER
# ==========================================

st.markdown(
    """
    <h2 style="margin-bottom:0;">
        YANI<span style="color:#3B82F6;">DOLLARZ</span>
    </h2>
    <p style="
        font-size:13px;
        letter-spacing:2px;
        color:#94A3B8;
    ">
        FOOTBALL PREDICTIONS & ANALYTICS
    </p>
    """,
    unsafe_allow_html=True
)

# Navigation menu
nav1, nav2, nav3 = st.columns([3, 1, 1])

with nav1:
    if st.button(
        "⌂ Home",
        key="nav_home",
        use_container_width=True
    ):
        navigate("home")

with nav2:
    if st.button(
        "Login",
        key="nav_login",
        use_container_width=True
    ):
        navigate("login")

with nav3:
    if st.button(
        "Create Account",
        key="nav_register",
        use_container_width=True
    ):
        navigate("register")

st.divider()


# ==========================================
# 4. HOMEPAGE
# ==========================================

if st.session_state.page == "home":

    st.write("")
    st.write("")

    st.markdown(
        """
        <p style="
            color:#60A5FA;
            letter-spacing:4px;
            font-size:14px;
        ">
            FOOTBALL PREDICTIONS
        </p>

        <h1 style="
            font-size:52px;
            font-weight:800;
            line-height:1.3;
        ">
            SMARTER PREDICTIONS.<br>
            BETTER DECISIONS.
        </h1>

        <p style="
            font-size:18px;
            color:#CBD5E1;
            max-width:750px;
            line-height:1.8;
        ">
            Get detailed football match predictions,
            statistical analysis and risk insights
            for match results, goals, corners,
            bookings and more.
        </p>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button(
            "Login →",
            type="primary",
            key="home_login",
            use_container_width=True
        ):
            navigate("login")

    with col2:
        if st.button(
            "Create Account",
            key="home_register",
            use_container_width=True
        ):
            navigate("register")

    st.write("")
    st.write("")
    st.divider()

    # Website features
    st.subheader("What YANIDOLLARZ Offers")

    f1, f2, f3 = st.columns(3)

    with f1:
        st.markdown("### ⚽ Match Predictions")
        st.write(
            "Analyse match outcomes, goals, "
            "corners and bookings."
        )

    with f2:
        st.markdown("### 🛡️ Risk Analysis")
        st.write(
            "Understand prediction probabilities "
            "and uncertainty."
        )

    with f3:
        st.markdown("### 📊 Performance Tracking")
        st.write(
            "Track historical predictions "
            "and model performance."
        )


# ==========================================
# 5. LOGIN PAGE
# ==========================================

elif st.session_state.page == "login":

    left, middle, right = st.columns([1, 2, 1])

    with middle:

        st.write("")

        st.markdown(
            """
            <h2 style="text-align:center;">
                Welcome Back
            </h2>

            <p style="
                text-align:center;
                color:#94A3B8;
            ">
                Login to access your football
                predictions and analysis.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.write("")

        with st.form("login_form"):

            email = st.text_input(
                "Email Address",
                placeholder="Enter your email"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password"
            )

            remember = st.checkbox("Remember me")

            login_submit = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True
            )

            if login_submit:

                if not email or not password:
                    st.warning(
                        "Please enter your email and password."
                    )
                else:
                    st.info(
                        "Login authentication will be "
                        "connected in the next stage."
                    )

        st.write("")

        st.markdown(
            "<p style='text-align:center;'>OR</p>",
            unsafe_allow_html=True
        )

        # Google login placeholder
        if st.button(
            "🌐 Continue with Google",
            key="google_login",
            use_container_width=True
        ):
            st.info(
                "Google authentication will "
                "be configured later."
            )

        st.write("")

        if st.button(
            "Don't have an account? Sign Up",
            key="login_to_register",
            use_container_width=True
        ):
            navigate("register")

        if st.button(
            "← Back to Home",
            key="login_back",
            use_container_width=True
        ):
            navigate("home")


# ==========================================
# 6. CREATE ACCOUNT PAGE
# ==========================================

elif st.session_state.page == "register":

    left, middle, right = st.columns([1, 2, 1])

    with middle:

        st.write("")

        st.markdown(
            """
            <h2 style="text-align:center;">
                Create Your Account
            </h2>

            <p style="
                text-align:center;
                color:#94A3B8;
            ">
                Join YANIDOLLARZ and start
                analysing football matches.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.write("")

        with st.form("register_form"):

            username = st.text_input(
                "Username",
                placeholder="Choose a username"
            )

            email = st.text_input(
                "Email Address",
                placeholder="Enter your email"
            )

            password = st.text_input(
                "Create Password",
                type="password",
                placeholder="Create a password"
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Confirm your password"
            )

            register_submit = st.form_submit_button(
                "Create Account",
                type="primary",
                use_container_width=True
            )

            if register_submit:

                if (
                    not username
                    or not email
                    or not password
                    or not confirm_password
                ):
                    st.warning(
                        "Please complete all fields."
                    )

                elif password != confirm_password:
                    st.error(
                        "Passwords do not match."
                    )

                elif len(password) < 8:
                    st.warning(
                        "Password must contain at least "
                        "8 characters."
                    )

                else:
                    st.info(
                        "Account registration will be "
                        "connected in the next stage."
                    )

        st.write("")

        st.markdown(
            "<p style='text-align:center;'>OR</p>",
            unsafe_allow_html=True
        )

        if st.button(
            "🌐 Continue with Google",
            key="google_register",
            use_container_width=True
        ):
            st.info(
                "Google registration will "
                "be configured later."
            )

        st.write("")

        if st.button(
            "Already have an account? Login",
            key="register_to_login",
            use_container_width=True
        ):
            navigate("login")

        if st.button(
            "← Back to Home",
            key="register_back",
            use_container_width=True
        ):
            navigate("home")


# ==========================================
# 7. FOOTER
# ==========================================

st.write("")
st.write("")

st.markdown(
    """
    <div style="
        text-align:center;
        color:#64748B;
        font-size:12px;
        padding:20px;
    ">
        © 2026 YANIDOLLARZ |
        Football Predictions & Analytics
    </div>
    """,
    unsafe_allow_html=True
)
