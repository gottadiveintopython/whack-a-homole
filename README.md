## Known Issues

### Quitting the app with the Escape key sometimes prints a C-level error message

...especially when a sound effect is playing.

The message varies every time, and following ones have been confirmed:
 
- `corrupted size vs. prev_size in fastbins`
- `Fatal glibc error: pthread_mutex_lock.c:450 (__pthread_mutex_lock_full): assertion failed: e != ESRCH || !robust`
- `Fatal glibc error: tpp.c:83 (__pthread_tpp_change_priority): assertion failed: new_prio == -1 || (new_prio >= fifo_min_prio && new_prio <= fifo_max_prio)`
- `malloc(): invalid size (unsorted)`
- `The futex facility returned an unexpected error code.`
