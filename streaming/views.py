from django.http import HttpResponse

def dns_verification(request):
    html_content = 'DNS Powered by <font color="#006699"><a href="http://www.DNSexit.com">DNS</a> </font><a href="http://www.DNSexit.com"><font color="#FF6600">EXIT</font>.COM</a>'
    return HttpResponse(html_content)