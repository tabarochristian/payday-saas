$(document).ready(() => {
    toastr.options = {
        positionClass: "toast-bottom-right",
        extendedTimeOut: 1000,
        timeOut: 1500,
        closeButton: true,
        progressBar: true,
    };

    
    $(".datepicker").datepicker({
        regional: language,  // French language
        dateFormat: 'yy-mm-dd',
        changeMonth: true,
        changeYear: true,
        yearRange: "-100:+0",
        showButtonPanel: true,
        closeText: 'Clear',
        currentText: 'Today',
    });
    $('form').dirrty();

    $(window).on('beforeunload', function() {
        if ($('form').dirrty('isDirty')) {
            return 'You have unsaved changes. Are you sure you want to leave?';
        }
    });

    $('form').on('submit', () => $('form').dirrty('reset'));

    // CSRF token for AJAX requests
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'));
            }
        }
    });

    // Change the language
    document.querySelectorAll('li[class$="-item"]').forEach(li => {
        // Utility function to get cookie by name
        function getCookie(name) {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith(name + '='));
            return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : null;
        }

        li.addEventListener('click', () => {
        const method = li.dataset.method || 'POST';
        const value = li.dataset.value;
        const key = li.dataset.key;
        const url = li.dataset.url;

        if (!url || !key || typeof value === 'undefined') {
            console.error('Missing required data attributes.');
            return;
        }

        const csrfToken = getCookie('csrftoken');
        if (!csrfToken) {
            console.error('CSRF token not found in cookies.');
            return;
        }

        // Construct JSON body
        const payload = {};
        payload[key] = value;

        const xhr = new XMLHttpRequest();
        xhr.open(method, url, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('X-CSRFToken', csrfToken); // Required by Django for JSON requests

        xhr.onreadystatechange = () => {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.status === 200) {
                    console.log('Success:', xhr.responseText);
                    location.reload(); // Refresh page on success
                } else {
                    console.error('Request failed:', xhr.status, xhr.responseText);
                }
            }
        };
        xhr.send(JSON.stringify(payload));
        });

    });

 
});