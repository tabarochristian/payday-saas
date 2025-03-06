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
    $('.lang-item').click(function() {
        const language = $(this).data('value');
        const csrfToken = Cookies.get('csrftoken');

        $.ajax({
            url: change_language_url,
            type: 'POST',
            data: {
                language: language,
                // csrfmiddlewaretoken: csrfToken,
            },
            async: false,
            success: () => location.reload(),
            error: (xhr, status, error) => {
                toastr.error(`Error: ${error}`);
                console.log(xhr.responseText);
                console.log(error);
            }
        });
    });
    
});