$(document).ready(() => {
    let isModified = false;

    toastr.options = {
        positionClass: "toast-bottom-right",
        extendedTimeOut: 1000,
        timeOut: 1500,
        closeButton: true,
        progressBar: true,
    };

    $(".datepicker").datepicker();

    $('form :input').on('input', () => {
        isModified = true;
    });

    $('button[type="submit"]').on('click', function(e) {
        e.preventDefault();
        isModified = false;
        $(this).closest('form').submit();
    });

    $(window).on('beforeunload', (e) => {
        if (!isModified) return;
        const message = '{% trans "Vous avez des changements non sauvés. Êtes-vous sûr de vouloir partir ?" %}';
        e.returnValue = message;
        return message;
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
                csrfmiddlewaretoken: csrfToken,
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

    // CSRF token for AJAX requests
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'));
            }
        }
    });
});