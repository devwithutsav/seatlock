User
    id
    name
    mail
    state

Seat
    id
    no

Reservation
    id
    user_id
    seat_id
    status
        pending
        confirmed
        cancelled
        expired
    duration
    created_at
    updated_at

WaitList
    id
    user_id
    created_at
    current_status

Reservation
    id
    reservation_id
    previous_state
    current_state
    reason
    created_at