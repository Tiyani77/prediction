
    if (
        st.session_state.user is None
        or st.session_state.auth_session is None
    ):

        st.warning("Please log in first.")

        if st.button("Go to Login"):
            navigate("login")

    else:

        # Validate the current session with Supabase
        try:
            client = get_supabase()

            session = st.session_state.auth_session

            client.auth.set_session(
                session.access_token,
                session.refresh_token
            )

            refreshed = client.auth.get_session()

            if refreshed is None:
                raise ValueError("Session expired")

            verified = client.auth.get_user(
                refreshed.access_token
            )

            if verified.user is None:
                raise ValueError("Invalid user")

            st.session_state.user = verified.user
            st.session_state.auth_session = refreshed

        except Exception:
            st.session_state.user = None
            st.session_state.auth_session = None

            st.warning(
                "Your session has expired. "
                "Please log in again."
            )

            if st.button("Return to Login"):
                navigate("login")

            st.stop()

        user = st.session_state.user

        username = (
            user.user_metadata.get("username")
            if user.user_metadata
            else None
        )

        if not username:
            username = (
                user.email.split("@")[0]
                if user.email
                else "Football Fan"
            )

        st.title(f"Welcome, {username}! ⚽")

        st.write(
            "You have successfully logged "
            "into YANIDOLLARZ."
        )

        st.divider()

        st.subheader("Your Football Dashboard")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.info(
                "⚽ Match Predictions — Coming Soon"
            )

        with col2:
            st.info(
                "📊 Risk Analysis — Coming Soon"
            )

        with col3:
            st.info(
                "📅 Upcoming Fixtures — Coming Soon"
            )

        st.write("")

        if st.button(
            "Logout",
            type="primary",
            use_container_width=True
        ):
            logout()


# ==========================================
# 11. FOOTER
# ==========================================

st.write("")
st.write("")

st.markdown("""
<div style="
    text-align:center;
    color:#64748B;
    font-size:12px;
    padding:20px;
">
    © 2026 YANIDOLLARZ |
    Football Predictions & Analytics
</div>
""", unsafe_allow_html=True)
